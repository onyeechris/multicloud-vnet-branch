from typing import List

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.nat_gateway import NatGatewayRequest
from app.pulumi_programs.nat_gateway import create_nat_gateway_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/nat-gateway", tags=["NAT Gateway"])


@router.get("", response_model=List[StackResponse])
def list_nat_gateways():
    """List all NAT Gateway stacks."""
    try:
        all_stacks = stack_list()
        location_h = get_location()
        vipes = [stack for stack in all_stacks if "nat_gateway_id" in stack["outputs"] and stack["outputs"].get("nat_location")==location_h]
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in vipes
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_nat_gateway(req: NatGatewayRequest):
    """Create a NAT Gateway stack (provisions a Standard Public IP + the NAT Gateway)."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="NAT Gateway already exist")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected")
    try:
        program = create_nat_gateway_program(
            req.name, req.resource_group_name, req.idle_timeout_in_minutes, req.zones, location, req.tags
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
def get_nat_gateway(stack_name: str):
    """Fetch outputs of an existing NAT Gateway stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_nat_gateway(stack_name: str, req: NatGatewayRequest):
#     """Update an existing NAT Gateway stack."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         program = create_nat_gateway_program(
#             req.name, req.resource_group_name, req.idle_timeout_in_minutes, req.zones, location, req.tags
#         )
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))
#
#
# @router.patch("/{stack_name}", response_model=StackResponse)
# def patch_nat_gateway(stack_name: str, req: NatGatewayPatchRequest):
#     """Partially update a NAT Gateway stack — only send the fields you want to change."""
#     if req.stack is not None and req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     try:
#         current = stack_outputs(stack_name)
#         location = req.location or get_location() or stack_location(stack_name)
#         name = req.name if req.name is not None else current.get("name", stack_name)
#         resource_group_name = req.resource_group_name if req.resource_group_name is not None else current.get("resource_group_name")
#         if resource_group_name is None:
#             raise HTTPException(status_code=422, detail="resource_group_name could not be resolved from stack outputs; provide it in the request body")
#         idle_timeout_in_minutes = (
#             req.idle_timeout_in_minutes
#             if req.idle_timeout_in_minutes is not None
#             else current.get("idle_timeout_in_minutes", 4)
#         )
#         if req.zones is not None:
#             zones = req.zones or None
#         else:
#             raw_zones = current.get("zones")
#             zones = raw_zones if raw_zones else None
#         tags = req.tags if req.tags is not None else {}
#         program = create_nat_gateway_program(
#             name, resource_group_name, idle_timeout_in_minutes, zones, location, tags
#         )
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except HTTPException:
#         raise
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_nat_gateway(stack_name: str):
    """Destroy the NAT Gateway stack (also deletes the Public IP it created)."""
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
