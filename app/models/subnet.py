from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional


class SubnetConfig(BaseModel):
    name: str = Field(..., description="Subnet name (unique within the VNet)")
    address_prefix: str = Field(..., description="Subnet CIDR e.g. 10.10.1.0/24")
    nsg_id: Optional[str] = Field(None, description="Optional NSG resource ID — alternative to nsg_stack")
    nsg_stack: Optional[str] = Field(None, description="Pulumi stack name exporting nsg_id — alternative to nsg_id")
    route_table_id: Optional[str] = Field(None, description="Optional Route Table resource ID — alternative to route_table_stack")
    route_table_stack: Optional[str] = Field(None, description="Pulumi stack name exporting route_table_id — alternative to route_table_id")
    nat_gateway_id: Optional[str] = Field(None, description="Optional NAT Gateway resource ID — alternative to nat_gateway_stack")
    nat_gateway_stack: Optional[str] = Field(None, description="Pulumi stack name exporting nat_gateway_id — alternative to nat_gateway_id")

    @model_validator(mode="after")
    def validate_refs(self) -> "SubnetConfig":
        for raw, stack, label in [
            (self.nsg_id, self.nsg_stack, "nsg"),
            (self.route_table_id, self.route_table_stack, "route_table"),
            (self.nat_gateway_id, self.nat_gateway_stack, "nat_gateway"),
        ]:
            if raw and stack:
                raise ValueError(f"Set only one of {label}_id or {label}_stack, not both")
        return self


class SubnetRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    vnet_name: str = Field(..., description="Parent VNet name — the VNet stack's 'name' (base name); the '-vnet' suffix is added automatically if missing")
    subnets: List[SubnetConfig] = Field(
        ..., min_length=1,
        description="One entry = single subnet. Multiple entries = multi-subnet stack."
    )
    # tags: Dict[str, str] = {}


class SubnetPatchRequest(BaseModel):
    stack: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    resource_group_name: Optional[str] = None
    vnet_name: Optional[str] = None
    subnets: Optional[List[SubnetConfig]] = None
    # tags: Optional[Dict[str, str]] = None
