from typing import List

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.vnet import VnetRequest, VnetPatchRequest
from app.pulumi_programs.vnet import create_vnet_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/vnet", tags=["VNet"])


@router.get("", response_model=List[StackResponse])
def list_vnets():
    """List all VNet stacks."""
    try:
        all_stacks = stack_list()
        location_h = get_location()
        vipes = [stack for stack in all_stacks if "vnet_name" in stack["outputs"] and stack["outputs"].get("vnet_location") == location_h]
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"]) for s in vipes]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_vnet(req: VnetRequest):
    """Create a new VNet stack."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="VNet already exist")
    location = req.location or get_location()
    if location is None:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected.")
    try:
        program = create_vnet_program(
            name=req.name,
            resource_group_name=req.resource_group_name,
            address_spaces=req.address_spaces,
            dns_servers=req.dns_servers,
            location=location,
            tags=req.tags
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
def get_vnet(stack_name: str):
    """Fetch outputs of an existing VNet stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_vnet(stack_name: str, req: VnetRequest):
#     """Update an existing VNet stack (Pulumi diffs and applies changes)."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected.")
#     try:
#         program = create_vnet_program(
#             name=req.name,
#             resource_group_name=req.resource_group_name,
#             address_spaces=req.address_spaces,
#             dns_servers=req.dns_servers,
#             location=location,
#             tags=req.tags,
#         )
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{stack_name}", response_model=StackResponse)
def patch_vnet(stack_name: str, req: VnetPatchRequest):
    """Partially update a VNet stack — only send the fields you want to change."""
    if req.stack is not None and req.stack != stack_name:
        raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
    try:
        current = stack_outputs(stack_name)
        location = current.get("vnet_location")
        name = current.get("name", stack_name)
        resource_group_name = current.get("resource_group_name")
        if resource_group_name is None:
            raise HTTPException(status_code=422, detail="resource_group_name could not be resolved")
        address_spaces =  current.get("address_spaces")
        if address_spaces is None:
            raise HTTPException(status_code=422, detail="address_spaces(vnet cidr) could not be resolved")
        dns_servers = req.dns_servers or current.get("dns_servers", [])
        tags = req.tags if req.tags is not None else current.get("tags", {})
        program = create_vnet_program(name, resource_group_name, address_spaces, dns_servers, location, tags)
        outputs = stack_up_safe(stack_name, location, program)
        return StackResponse(status="updated", stack=stack_name, outputs=outputs)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_vnet(stack_name: str):
    """Destroy the VNet stack and all its resources."""
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
