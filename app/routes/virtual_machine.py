from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.virtual_machine import VirtualMachineRequest, VirtualMachinePatchRequest, ImageReference
from app.pulumi_programs.virtual_machine import create_virtual_machine_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/virtual-machine", tags=["Virtual Machine"])


def _resolve_public_key_from_stack(kp_stack: str) -> str:
    """Pull `public_key_openssh` from a key-pair stack's outputs."""
    try:
        outputs = stack_outputs(kp_stack)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not resolve key pair stack '{kp_stack}': {exc}")
    pub = outputs.get("public_key_openssh")
    if not pub:
        raise HTTPException(status_code=404, detail=f"public_key_openssh not found in stack '{kp_stack}'")
    return pub


def _resolve_auth(
    admin_password: Optional[str],
    ssh_public_key: Optional[str],
    key_pair_stack: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Return (admin_password, ssh_public_key) after resolving key_pair_stack if used."""
    if key_pair_stack:
        return None, _resolve_public_key_from_stack(key_pair_stack)
    return admin_password, ssh_public_key


def _resolve_nsg_id_from_stack(nsg_stack: str) -> str:
    """Pull `nsg_id` from an NSG stack's outputs."""
    try:
        outputs = stack_outputs(nsg_stack)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not resolve NSG stack '{nsg_stack}': {exc}")
    nsg_id = outputs.get("nsg_id")
    if not nsg_id:
        raise HTTPException(status_code=404, detail=f"nsg_id not found in stack '{nsg_stack}'")
    return nsg_id


def _resolve_nsg(nsg_id: Optional[str], nsg_stack: Optional[str]) -> Optional[str]:
    """Return the final nsg_id, resolving from a stack name if `nsg_stack` is set."""
    if nsg_stack:
        return _resolve_nsg_id_from_stack(nsg_stack)
    return nsg_id


@router.get("", response_model=List[StackResponse])
def list_virtual_machines():
    """List all Virtual Machine stacks."""
    try:
        all_stacks = stack_list()
        location = get_location()
        vipes = [stack for stack in all_stacks if "vm_id" in stack["outputs"] and stack["outputs"].get("vm_location") == location]
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in vipes
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_virtual_machine(req: VirtualMachineRequest):
    """Provision a Virtual Machine (with NIC and optional Public IP). Auth: password, raw ssh key, or key-pair stack."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="Virtual Machine already exist")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected.")
    try:
        admin_password, ssh_public_key = _resolve_auth(req.admin_password, req.ssh_public_key, req.key_pair_stack)
        nsg_id = _resolve_nsg(req.nsg_id, req.nsg_stack)
        program = create_virtual_machine_program(
            req.name, req.resource_group_name, req.subnet_id, req.vm_size,
            req.admin_username, admin_password, ssh_public_key, req.key_pair_stack,
            req.create_public_ip, nsg_id, req.image, location, req.tags,
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
def get_virtual_machine(stack_name: str):
    """Fetch outputs of an existing Virtual Machine stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_virtual_machine(stack_name: str, req: VirtualMachineRequest):
#     """Update an existing Virtual Machine stack."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         admin_password, ssh_public_key = _resolve_auth(req.admin_password, req.ssh_public_key, req.key_pair_stack)
#         nsg_id = _resolve_nsg(req.nsg_id, req.nsg_stack)
#         program = create_virtual_machine_program(
#             req.name, req.resource_group_name, req.subnet_id, req.vm_size,
#             req.admin_username, admin_password, ssh_public_key, req.key_pair_stack,
#             req.create_public_ip, nsg_id, req.image, location, req.tags,
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
def patch_virtual_machine(stack_name: str, req: VirtualMachinePatchRequest):
    """Partially update a Virtual Machine stack — only send the fields you want to change."""
    if req.stack is not None and req.stack != stack_name:
        raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
    try:
        current = stack_outputs(stack_name)
        location = req.location or get_location() or current.get("vm_location")
        name = req.name if req.name is not None else current.get("name", stack_name)
        resource_group_name = current.get("resource_group_name")
        if resource_group_name is None:
            raise HTTPException(status_code=422, detail="resource_group_name could not be resolved from stack outputs; provide it in the request body")
        subnet_id = current.get("subnet_id")
        if subnet_id is None:
            raise HTTPException(status_code=422, detail="subnet_id could not be resolved from stack outputs; provide it in the request body")
        vm_size = req.vm_size if req.vm_size is not None else current.get("vm_size", "Standard_B1s")
        admin_username = current.get("admin_username")
        if admin_username is None:
            raise HTTPException(status_code=422, detail="admin_username could not be resolved from stack outputs; provide it in the request body")

        # Auth resolution. Patch can flip auth method, but we need exactly one to be set.
        key_pair_stack = current.get("key_pair_stack")
        admin_password = req.admin_password
        ssh_public_key = req.ssh_public_key
        if admin_password is None and ssh_public_key is None and not key_pair_stack:
            raise HTTPException(
                status_code=422,
                detail="Provide one of admin_password, ssh_public_key, or key_pair_stack — secrets cannot be recovered from stack outputs",
            )
        admin_password, ssh_public_key = _resolve_auth(admin_password, ssh_public_key, key_pair_stack)

        # create_public_ip = req.create_public_ip if req.create_public_ip is not None else current.get("create_public_ip", True)
        create_public_ip = current.get("create_public_ip")
        if req.nsg_id is not None or req.nsg_stack is not None:
            if req.nsg_id and req.nsg_stack:
                raise HTTPException(status_code=400, detail="Set only one of nsg_id or nsg_stack, not both")
            nsg_id = _resolve_nsg(req.nsg_id, req.nsg_stack)
        else:
            nsg_id = current.get("nsg_id")
        raw_image = current.get("image")
        image = ImageReference(**raw_image) if raw_image else ImageReference()
        # if req.image is not None:
        #     image = req.image
        # else:
        #     raw = current.get("image")
        #     image = ImageReference(**raw) if raw else ImageReference()
        tags = req.tags if req.tags is not None else {}
        program = create_virtual_machine_program(
            name, resource_group_name, subnet_id, vm_size, admin_username,
            admin_password, ssh_public_key, key_pair_stack,
            create_public_ip, nsg_id, image, location, tags,
        )
        outputs = stack_up_safe(stack_name, location, program)
        return StackResponse(status="updated", stack=stack_name, outputs=outputs)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_virtual_machine(stack_name: str):
    """Destroy the Virtual Machine stack."""
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
