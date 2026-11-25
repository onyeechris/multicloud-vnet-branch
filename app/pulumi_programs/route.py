from typing import Dict, List, Optional
import pulumi
import pulumi_azure_native as azure_native
from app.utils.location_state import get_location

from app.models.route import RouteEntry


def create_route_program(
    name: str,
    resource_group_name: str,
    route_table_name: str,
    routes: List[RouteEntry],
    location: Optional[str],
    tags: Dict[str, str],
):
    if location is None:
        location = get_location()
    def program():
        created_ids = []
        created_names = []
        for i, r in enumerate(routes):
            kwargs: Dict = {
                "resource_group_name": resource_group_name,
                "route_table_name": route_table_name,
                "route_name": r.name,
                "address_prefix": r.address_prefix,
                "next_hop_type": r.next_hop_type,
            }
            if r.next_hop_ip_address:
                kwargs["next_hop_ip_address"] = r.next_hop_ip_address
            route = azure_native.network.Route(f"{name}-route-{i + 1}", **kwargs)
            created_ids.append(route.id)
            created_names.append(route.name)

        pulumi.export("route_ids", created_ids)
        pulumi.export("route_names", created_names)
        pulumi.export("route_entries", [
            {
                "name": r.name,
                "address_prefix": r.address_prefix,
                "next_hop_type": r.next_hop_type,
                "next_hop_ip_address": r.next_hop_ip_address,
            }
            for r in routes
        ])
        pulumi.export("route_table_name", route_table_name)
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("name", name)
        pulumi.export("route_location", location)

    return program
