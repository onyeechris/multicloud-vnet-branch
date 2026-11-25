from typing import List

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.resource_group import ResourceGroupRequest
from app.pulumi_programs.resource_group import create_resource_group_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/resource-group", tags=["Resource Group"])


@router.get("", response_model=List[StackResponse])
def list_resource_groups():
    """List all Resource Group stacks."""
    try:
        all_stacks = stack_list()
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in all_stacks if "resource_group_id" in s["outputs"]
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_resource_group(req: ResourceGroupRequest):
    """Create a new Resource Group stack."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="Resource Group already exist")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
    try:
        program = create_resource_group_program(req.name, location, req.tags)
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
def get_resource_group(stack_name: str):
    """Fetch outputs of an existing Resource Group stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_resource_group(stack_name: str, req: ResourceGroupRequest):
#     """Update an existing Resource Group stack."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         program = create_resource_group_program(req.name, location, req.tags)
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))
#
#
# @router.patch("/{stack_name}", response_model=StackResponse)
# def patch_resource_group(stack_name: str, req: ResourceGroupPatchRequest):
#     """Partially update a Resource Group stack — only send the fields you want to change."""
#     if req.stack is not None and req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     try:
#         current = stack_outputs(stack_name)
#         location = req.location or get_location() or stack_location(stack_name)
#         name = req.name if req.name is not None else current.get("name", stack_name)
#         tags = req.tags if req.tags is not None else {}
#         program = create_resource_group_program(name, location, tags)
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


# Order matches Azure dependency teardown: VM → key-pair → subnet → NAT → route →
# route-table → NSG → VNet. Each tuple is (required output, excluded output) — the
# excluded key disambiguates types that share an output (e.g. VM also exports nsg_id).
_DEPENDENT_TYPES_ORDER = [
    ("vm_id", None),
    ("ssh_public_key_id", None),
    ("subnet_ids", None),
    ("nat_gateway_id", None),
    ("route_ids", None),
    ("route_table_id", None),
    ("nsg_id", "vm_id"),
    ("vnet_id", None),
]


@router.delete("/{stack_name}")
def delete_resource_group(stack_name: str):
    """Destroy the Resource Group stack and cascade-delete every dependent stack
    (VM, key-pair, subnet, NAT, route, route-table, NSG, VNet) that references it."""
    try:
        if not stack_exists(stack_name):
            raise HTTPException(status_code=404, detail=f"Resource Group stack '{stack_name}' does not exist")
        rg_outputs = stack_outputs(stack_name)
        rg_name = rg_outputs.get("resource_group_name") or rg_outputs.get("name")
        all_stacks = stack_list()
        cascade_deleted = []
        for include_key, exclude_key in _DEPENDENT_TYPES_ORDER:
            for s in all_stacks:
                outs = s["outputs"]
                if include_key not in outs:
                    continue
                if exclude_key is not None and exclude_key in outs:
                    continue
                if outs.get("resource_group_name") != rg_name:
                    continue
                if stack_exists(s["name"]):
                    stack_destroy(s["name"])
                    cascade_deleted.append(s["name"])
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name, "cascade_deleted": cascade_deleted}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
