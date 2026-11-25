from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional

VALID_NEXT_HOP_TYPES = {"Internet", "VirtualAppliance", "VirtualNetworkGateway", "VnetLocal", "None"}


class RouteEntry(BaseModel):
    name: str = Field(..., description="Route name (unique within the route table)")
    address_prefix: str = Field(..., description="Destination CIDR e.g. 0.0.0.0/0")
    next_hop_type: str = Field(
        ...,
        description="One of: Internet, VirtualAppliance, VirtualNetworkGateway, VnetLocal, None",
    )
    next_hop_ip_address: Optional[str] = Field(
        None,
        description="Required when next_hop_type='VirtualAppliance' — the NVA's IP",
    )

    @model_validator(mode="after")
    def validate_next_hop(self) -> "RouteEntry":
        if self.next_hop_type not in VALID_NEXT_HOP_TYPES:
            raise ValueError(f"next_hop_type must be one of {sorted(VALID_NEXT_HOP_TYPES)}")
        if self.next_hop_type == "VirtualAppliance" and not self.next_hop_ip_address:
            raise ValueError("next_hop_ip_address is required when next_hop_type='VirtualAppliance'")
        if self.next_hop_type != "VirtualAppliance" and self.next_hop_ip_address:
            raise ValueError("next_hop_ip_address is only valid when next_hop_type='VirtualAppliance'")
        return self


class RouteRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    route_table_name: Optional[str] = Field(
        None,
        description="Parent route table name (from RouteTable stack outputs.route_table_name) — set this OR route_table_stack",
    )
    route_table_stack: Optional[str] = Field(
        None,
        description="Pulumi stack name of the route table — the backend resolves route_table_name from its outputs",
    )
    routes: List[RouteEntry] = Field(
        ..., min_length=1,
        description="One or more routes to add to the route table",
    )
    tags: Dict[str, str] = {}

    @model_validator(mode="after")
    def validate_rt_ref(self) -> "RouteRequest":
        if not self.route_table_name and not self.route_table_stack:
            raise ValueError("Provide route_table_name or route_table_stack")
        if self.route_table_name and self.route_table_stack:
            raise ValueError("Set only one of route_table_name or route_table_stack, not both")
        return self


class RoutePatchRequest(BaseModel):
    stack: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    resource_group_name: Optional[str] = None
    route_table_name: Optional[str] = None
    route_table_stack: Optional[str] = None
    routes: Optional[List[RouteEntry]] = None
    tags: Optional[Dict[str, str]] = None
