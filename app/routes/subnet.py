from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.subnet import SubnetRequest, SubnetPatchRequest, SubnetConfig
from app.pulumi_programs.subnet import create_subnet_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/subnet", tags=["Subnet"])


def _resolve_vnet_name(base_name: str) -> str:
    """VNet stacks always name the Azure resource '{name}-vnet' — apply the same suffix here."""
    return f"{base_name}-vnet"


def _resolve_output_from_stack(stack: str, output_key: str, kind: str) -> str:
    """Fetch a named output from another stack — used to resolve *_stack fields to IDs."""
    try:
        outputs = stack_outputs(stack)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not resolve {kind} stack '{stack}': {exc}")
    value = outputs.get(output_key)
    if not value:
        raise HTTPException(status_code=404, detail=f"{output_key} not found in stack '{stack}'")
    return value


def _resolve_subnet_refs(subnets: List[SubnetConfig]) -> List[SubnetConfig]:
    """Return a copy of subnets with *_stack fields resolved into *_id fields."""
    resolved = []
    for s in subnets:
        nsg_id = s.nsg_id
        if s.nsg_stack:
            nsg_id = _resolve_output_from_stack(s.nsg_stack, "nsg_id", "NSG")
        rt_id = s.route_table_id
        if s.route_table_stack:
            rt_id = _resolve_output_from_stack(s.route_table_stack, "route_table_id", "Route Table")
        nat_id = s.nat_gateway_id
        if s.nat_gateway_stack:
            nat_id = _resolve_output_from_stack(s.nat_gateway_stack, "nat_gateway_id", "NAT Gateway")
        resolved.append(SubnetConfig(
            name=s.name,
            address_prefix=s.address_prefix,
            nsg_id=nsg_id,
            route_table_id=rt_id,
            nat_gateway_id=nat_id,
        ))
    return resolved


@router.get("", response_model=List[StackResponse])
def list_subnets():
    """List all Subnet stacks."""
    try:
        all_stacks = stack_list()
        location_h = get_location()
        vipes = [stack for stack in all_stacks if "subnet_ids" in stack["outputs"] and stack["outputs"].get("subnet_location") == location_h]
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in vipes
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_subnet(req: SubnetRequest):
    """Create a subnet stack (single subnet if one entry, multiple if more) inside an existing VNet."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="Subnet already exist")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
    try:
        subnets = _resolve_subnet_refs(req.subnets)
        program = create_subnet_program(
            req.name, req.resource_group_name, _resolve_vnet_name(req.vnet_name), subnets, location
        )
        outputs = stack_up_safe(req.stack, location, program)
        return StackResponse(status="created", stack=req.stack, outputs=outputs)
    except Exception as exc:
        if stack_exists(req.stack):
            try:
                stack_destroy(req.stack)
            except Exception as exc2:
                raise HTTPException(
                    status_code=500,
                    detail=f"Original error: {exc}. Also failed to cleanup: {exc2}. Manually check stack {req.stack}"
                )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{stack_name}", response_model=StackResponse)
def get_subnet(stack_name: str):
    """Fetch outputs of an existing subnet stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_subnet(stack_name: str, req: SubnetRequest):
#     """Update an existing subnet stack."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         subnets = _resolve_subnet_refs(req.subnets)
#         program = create_subnet_program(
#             req.name, req.resource_group_name, _resolve_vnet_name(req.vnet_name), subnets, location, req.tags
#         )
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except HTTPException:
#         raise
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{stack_name}", response_model=StackResponse)
def patch_subnet(stack_name: str, req: SubnetPatchRequest):
    """Partially update a subnet stack — only send the fields you want to change."""
    if req.stack is not None and req.stack != stack_name:
        raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
    try:
        current = stack_outputs(stack_name)
        location = req.location or get_location() or stack_location(stack_name)
        name = req.name if req.name is not None else current.get("name", stack_name)
        resource_group_name = current.get("resource_group_name")
        if resource_group_name is None:
            raise HTTPException(status_code=422, detail="resource_group_name could not be resolved from stack outputs; provide it in the request body")
        vnet_name = current.get("vnet_name")
        if vnet_name is None:
            raise HTTPException(status_code=422, detail="vnet_name could not be resolved from stack outputs; provide it in the request body")
        if req.subnets is not None:
            subnets = _resolve_subnet_refs(req.subnets)
        else:
            raw = current.get("subnet_configs")
            if not raw:
                raise HTTPException(status_code=422, detail="subnets could not be resolved from stack outputs; provide them in the request body")
            subnets = [SubnetConfig(**s) for s in raw]
        # tags = req.tags if req.tags is not None else current.get("tags", {})
        program = create_subnet_program(name, resource_group_name, vnet_name, subnets, location)
        outputs = stack_up_safe(stack_name, location, program)
        return StackResponse(status="updated", stack=stack_name, outputs=outputs)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_subnet(stack_name: str):
    """Destroy the subnet stack."""
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
