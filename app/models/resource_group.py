from pydantic import BaseModel, Field
from typing import Dict, Optional


class ResourceGroupRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource group name")
    tags: Dict[str, str] = {}

#
# class ResourceGroupPatchRequest(BaseModel):
#     stack: Optional[str] = None
#     location: Optional[str] = None
#     name: Optional[str] = None
#     tags: Optional[Dict[str, str]] = None
