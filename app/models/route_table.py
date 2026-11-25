from pydantic import BaseModel, Field
from typing import Dict, Optional


class RouteTableRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    disable_bgp_route_propagation: bool = Field(
        False,
        description="Disable propagation of routes learned from BGP via a VirtualNetworkGateway",
    )
    tags: Dict[str, str] = {}


class RouteTablePatchRequest(BaseModel):
    stack: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    resource_group_name: Optional[str] = None
    disable_bgp_route_propagation: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None
