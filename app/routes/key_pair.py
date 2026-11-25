import io
import os
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.common import StackResponse
from app.models.key_pair import KeyPairRequest
from app.pulumi_programs.key_pair import create_key_pair_program
from app.utils.location_state import get_location
from app.utils.stack import (
    stack_up_safe, stack_outputs, stack_destroy,
    stack_list, stack_location, stack_exists,
)

router = APIRouter(prefix="/key-pair", tags=["Key Pair"])


def _keyvault_secret_client(vault_uri: str):
    """Build a Key Vault SecretClient using the same ARM_* service-principal env vars Pulumi uses."""
    try:
        from azure.identity import ClientSecretCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"azure-identity / azure-keyvault-secrets not installed: {exc}",
        )

    tenant_id = os.getenv("ARM_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("ARM_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("ARM_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET")
    if not (tenant_id and client_id and client_secret):
        raise HTTPException(
            status_code=500,
            detail="ARM_TENANT_ID / ARM_CLIENT_ID / ARM_CLIENT_SECRET must be set to access Key Vault",
        )

    credential = ClientSecretCredential(
        tenant_id=tenant_id, client_id=client_id, client_secret=client_secret,
    )
    return SecretClient(vault_url=vault_uri, credential=credential)


@router.get("", response_model=List[StackResponse])
def list_key_pairs():
    """List all key pair stacks."""
    try:
        all_stacks = stack_list()
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in all_stacks if "key_name" in s["outputs"] and "key_vault_uri" in s["outputs"]
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_key_pair(req: KeyPairRequest):
    """Create a new SSH key pair and store the private key in Azure Key Vault."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail=f"Key pair stack '{req.stack}' already exists")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
    try:
        program = create_key_pair_program(req.name, req.resource_group_name, location, req.tags)
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


@router.get("/{stack_name}/download")
def download_key_pair(stack_name: str):
    """Download the private key PEM file from Azure Key Vault."""
    if not stack_exists(stack_name):
        raise HTTPException(status_code=404, detail=f"Stack '{stack_name}' not found")

    try:
        outputs = stack_outputs(stack_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    vault_uri = outputs.get("key_vault_uri")
    secret_name = outputs.get("private_key_secret_name")
    key_name = outputs.get("key_name", stack_name)
    if not vault_uri or not secret_name:
        raise HTTPException(status_code=404, detail="key_vault_uri / private_key_secret_name missing from stack outputs")

    try:
        client = _keyvault_secret_client(vault_uri)
        pem = client.get_secret(secret_name).value
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve private key from Key Vault: {exc}")

    return StreamingResponse(
        io.BytesIO(pem.encode()),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{key_name}.pem"'},
    )


@router.get("/{stack_name}", response_model=StackResponse)
def get_key_pair(stack_name: str):
    """Fetch outputs of an existing key pair stack."""
    if not stack_exists(stack_name):
        raise HTTPException(status_code=404, detail=f"Stack '{stack_name}' not found")
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_key_pair(stack_name: str, req: KeyPairRequest):
#     """Update an existing key pair stack (re-generates if inputs changed)."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         program = create_key_pair_program(req.name, req.resource_group_name, location, req.tags)
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))
#
#
# @router.patch("/{stack_name}", response_model=StackResponse)
# def patch_key_pair(stack_name: str, req: KeyPairPatchRequest):
#     """Partially update a key pair stack — only send the fields you want to change."""
#     if req.stack is not None and req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     try:
#         current = stack_outputs(stack_name)
#         location = req.location or get_location() or stack_location(stack_name)
#         name = req.name if req.name is not None else current.get("name", stack_name)
#         resource_group_name = req.resource_group_name if req.resource_group_name is not None else current.get("resource_group_name")
#         if resource_group_name is None:
#             raise HTTPException(status_code=422, detail="resource_group_name could not be resolved from stack outputs; provide it in the request body")
#         tags = req.tags if req.tags is not None else {}
#         program = create_key_pair_program(name, resource_group_name, location, tags)
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except HTTPException:
#         raise
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_key_pair(stack_name: str):
    """Destroy the key pair stack and all associated Azure resources (Key Vault + secret)."""
    if not stack_exists(stack_name):
        raise HTTPException(status_code=404, detail=f"Stack '{stack_name}' not found")
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
