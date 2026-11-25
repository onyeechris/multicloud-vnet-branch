from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class NatGatewayRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    idle_timeout_in_minutes: int = Field(
        4,
        ge=4, le=120,
        description="Idle timeout in minutes (4–120)",
    )
    zones: Optional[List[str]] = Field(
        None,
        description="Availability zones e.g. ['1'] — leave unset for regional (non-zonal)",
    )
    tags: Dict[str, str] = {}


# class NatGatewayPatchRequest(BaseModel):
#     stack: Optional[str] = None
#     location: Optional[str] = None
#     name: Optional[str] = None
#     resource_group_name: Optional[str] = None
#     idle_timeout_in_minutes: Optional[int] = None
#     zones: Optional[List[str]] = None
#     tags: Optional[Dict[str, str]] = None
