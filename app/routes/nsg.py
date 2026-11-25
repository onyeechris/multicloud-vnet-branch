from typing import List

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.nsg import NsgRequest, NsgPatchRequest, SecurityRule
from app.pulumi_programs.nsg import create_nsg_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/nsg", tags=["Network Security Group"])


@router.get("", response_model=List[StackResponse])
def list_nsgs():
    """List all Network Security Group stacks."""
    try:
        all_stacks = stack_list()
        location_h = get_location()
        vipes = [stack for stack in all_stacks if "nsg_id" in stack["outputs"] and stack["outputs"].get("nsg_location") == location_h]
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in vipes
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_nsg(req: NsgRequest):
    """Create a Network Security Group with optional rules."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="NSG already exist")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected")
    try:
        program = create_nsg_program(req.name, req.resource_group_name, req.security_rules, location, req.tags)
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
def get_nsg(stack_name: str):
    """Fetch outputs of an existing NSG stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_nsg(stack_name: str, req: NsgRequest):
#     """Update an existing NSG stack."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         program = create_nsg_program(req.name, req.resource_group_name, req.security_rules, location, req.tags)
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{stack_name}", response_model=StackResponse)
def patch_nsg(stack_name: str, req: NsgPatchRequest):
    """Partially update an NSG stack — only send the fields you want to change."""
    if req.stack is not None and req.stack != stack_name:
        raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
    try:
        current = stack_outputs(stack_name)
        location = current.get("nsg_location")
        name = req.name if req.name is not None else current.get("name", stack_name)
        resource_group_name = current.get("resource_group_name")
        if resource_group_name is None:
            raise HTTPException(status_code=422, detail="resource_group_name could not be resolved from stack outputs")
        if req.security_rules is not None:
            security_rules = req.security_rules
        else:
            raw = req.security_rules if req.security_rules is not None else current.get("security_rules", [])
            security_rules = [SecurityRule(**r) for r in raw]
        tags = req.tags if req.tags is not None else current.get("tags", {})
        program = create_nsg_program(name, resource_group_name, security_rules, location, tags)
        outputs = stack_up_safe(stack_name, location, program)
        return StackResponse(status="updated", stack=stack_name, outputs=outputs)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_nsg(stack_name: str):
    """Destroy the NSG stack."""
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
