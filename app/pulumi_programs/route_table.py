from typing import Dict, Optional
import pulumi
import pulumi_azure_native as azure_native
from app.utils.location_state import get_location


def create_route_table_program(
    name: str,
    resource_group_name: str,
    disable_bgp_route_propagation: bool,
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        resolved_location = location or get_location()
        if not resolved_location:
            raise ValueError("No location provided and no active location selected.")
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": f"{name}-rt"}
        kwargs: Dict = {
            "resource_group_name": resource_group_name,
            "route_table_name": f"{name}-rt",
            "disable_bgp_route_propagation": disable_bgp_route_propagation,
            "location": resolved_location,
            "tags": base_tags
        }

        rt = azure_native.network.RouteTable(f"{name}-rt", **kwargs)
        pulumi.export("route_table_id", rt.id)
        pulumi.export("route_table_name", rt.name)
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("disable_bgp_route_propagation", disable_bgp_route_propagation)
        pulumi.export("name", name)
        pulumi.export("tags", rt.tags)
        pulumi.export("rt_location", location)

    return program
