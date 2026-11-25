from typing import Dict, List, Optional
import pulumi
import pulumi_azure_native as azure_native
from app.utils.location_state import get_location


def create_vnet_program(
    name: str,
    resource_group_name: str,
    address_spaces: List[str],
    dns_servers: List[str],
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        resolved_location = location or get_location()
        if not resolved_location:
            raise ValueError("No location provided and no active location selected.")
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": name}
        kwargs = {
            "resource_group_name": resource_group_name,
            "virtual_network_name": f"{name}-vnet",
            "address_space": azure_native.network.AddressSpaceArgs(
                address_prefixes=address_spaces,
            ),
            "tags": base_tags,
            "location": resolved_location,
        }

        if dns_servers:
            kwargs["dhcp_options"] = azure_native.network.DhcpOptionsArgs(
                dns_servers=dns_servers,
            )
        vnet = azure_native.network.VirtualNetwork(f"{name}-vnet", **kwargs)
        pulumi.export("vnet_id", vnet.id)
        pulumi.export("vnet_name", vnet.name)
        pulumi.export("address_spaces", address_spaces)
        pulumi.export("dns_servers", dns_servers)
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("name", name)
        pulumi.export("vnet_location", resolved_location)
        pulumi.export("tags", vnet.tags)

    return program
