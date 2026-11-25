from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class VnetRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    address_spaces: List[str] = Field(..., min_length=1, description="VNet CIDR blocks e.g. ['10.0.0.0/16']")
    dns_servers: List[str] = Field(default=[], description="Custom DNS servers")
    tags: Dict[str, str] = {}

class VnetPatchRequest(BaseModel):
    stack: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    resource_group_name: Optional[str] = None
    address_spaces: Optional[List[str]] = None
    dns_servers: Optional[List[str]] = None
    tags: Optional[Dict[str, str]] = None
