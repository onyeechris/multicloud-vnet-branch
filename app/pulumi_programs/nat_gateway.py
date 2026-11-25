from typing import Dict, List, Optional
import pulumi
import pulumi_azure_native as azure_native
from app.utils.location_state import get_location


def create_nat_gateway_program(
    name: str,
    resource_group_name: str,
    idle_timeout_in_minutes: int,
    zones: Optional[List[str]],
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        resolved_location = location or get_location()
        if not resolved_location:
            raise ValueError("No location provided and no active location selected.")
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": f"{name}-nat"}

        pip_kwargs: Dict = {
            "resource_group_name": resource_group_name,
            "public_ip_address_name": f"{name}-nat-pip",
            "public_ip_allocation_method": "Static",
            "sku": azure_native.network.PublicIPAddressSkuArgs(name="Standard"),
            "tags": base_tags,
            "location": resolved_location
        }
        if zones:
            pip_kwargs["zones"] = zones
        pip = azure_native.network.PublicIPAddress(f"{name}-nat-pip", **pip_kwargs)

        nat_kwargs: Dict = {
            "resource_group_name": resource_group_name,
            "nat_gateway_name": f"{name}-nat",
            "sku": azure_native.network.NatGatewaySkuArgs(name="Standard"),
            "idle_timeout_in_minutes": idle_timeout_in_minutes,
            "public_ip_addresses": [azure_native.network.SubResourceArgs(id=pip.id)],
            "tags": base_tags,
            "location": resolved_location
        }
        if zones:
            nat_kwargs["zones"] = zones
        nat = azure_native.network.NatGateway(f"{name}-nat", **nat_kwargs)

        pulumi.export("nat_gateway_id", nat.id)
        pulumi.export("nat_gateway_name", nat.name)
        pulumi.export("public_ip_id", pip.id)
        pulumi.export("public_ip_address", pip.ip_address)
        pulumi.export("idle_timeout_in_minutes", idle_timeout_in_minutes)
        pulumi.export("zones", zones or [])
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("name", name)
        pulumi.export("nat_location", location)

    return program
