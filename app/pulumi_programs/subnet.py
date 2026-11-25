from typing import Dict, List, Optional
import pulumi
import pulumi_azure_native as azure_native
from app.utils.location_state import get_location

from app.models.subnet import SubnetConfig


def create_subnet_program(
    name: str,
    resource_group_name: str,
    vnet_name: str,
    subnets: List[SubnetConfig],
    location: Optional[str]
):
    # base_tags = {"ManagedBy": "Pulumi", **tags, "Name": name}
    resolved_location = location or get_location()
    if not resolved_location:
        raise ValueError("No location provided and no active location selected.")
    def program():
        created_ids = []
        created_names = []
        for i, s in enumerate(subnets):
            kwargs: Dict = {
                "resource_group_name": resource_group_name,
                "virtual_network_name": vnet_name,
                "subnet_name": s.name,
                "address_prefix": s.address_prefix
                # "tags": base_tags,
            }
            if s.nsg_id:
                kwargs["network_security_group"] = azure_native.network.NetworkSecurityGroupArgs(
                    id=s.nsg_id,
                )
            if s.route_table_id:
                kwargs["route_table"] = azure_native.network.RouteTableArgs(
                    id=s.route_table_id,
                )
            if s.nat_gateway_id:
                kwargs["nat_gateway"] = azure_native.network.SubResourceArgs(
                    id=s.nat_gateway_id,
                )
            subnet = azure_native.network.Subnet(
                f"{name}-subnet-{i + 1}",
                **kwargs,
            )
            created_ids.append(subnet.id)
            created_names.append(subnet.name)

        pulumi.export("subnet_ids", created_ids)
        pulumi.export("subnet_names", created_names)
        pulumi.export("subnet_configs", [
            {
                "name": s.name,
                "address_prefix": s.address_prefix,
                "nsg_id": s.nsg_id,
                "route_table_id": s.route_table_id,
                "nat_gateway_id": s.nat_gateway_id,
            }
            for s in subnets
        ])
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("vnet_name", vnet_name)
        pulumi.export("name", name)
        pulumi.export("subnet_location", resolved_location)
        # pulumi.export("tags", subnet.tags)

    return program
