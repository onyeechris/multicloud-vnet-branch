from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class SecurityRule(BaseModel):
    name: str = Field(..., description="Rule name")
    priority: int = Field(..., description="Priority (100–4096)")
    direction: str = Field("Inbound", description="Inbound or Outbound")
    access: str = Field("Allow", description="Allow or Deny")
    protocol: str = Field("Tcp", description="Tcp, Udp, Icmp, Esp, * etc.")
    source_address_prefix: str = "*"
    source_port_range: str = "*"
    destination_address_prefix: str = "*"
    destination_port_range: str = "*"
    description: Optional[str] = None


class NsgRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    security_rules: List[SecurityRule] = Field(default=[], description="Optional NSG rules")
    tags: Dict[str, str] = {}


class NsgPatchRequest(BaseModel):
    stack: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    resource_group_name: Optional[str] = None
    security_rules: Optional[List[SecurityRule]] = None
    tags: Optional[Dict[str, str]] = None
