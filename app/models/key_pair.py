from pydantic import BaseModel, Field
from typing import Dict, Optional


class KeyPairRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="SSH key pair name (also used as the Key Vault secret name)")
    resource_group_name: str = Field(..., description="Target resource group name")
    tags: Dict[str, str] = {}


# class KeyPairPatchRequest(BaseModel):
#     stack: Optional[str] = None
#     location: Optional[str] = None
#     name: Optional[str] = None
#     resource_group_name: Optional[str] = None
#     tags: Optional[Dict[str, str]] = None
