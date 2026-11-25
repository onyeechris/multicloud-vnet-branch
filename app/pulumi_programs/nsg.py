from typing import Dict, List, Optional
import pulumi
import pulumi_azure_native as azure_native

from app.models.nsg import SecurityRule
from app.utils.location_state import get_location

def create_nsg_program(
    name: str,
    resource_group_name: str,
    security_rules: List[SecurityRule],
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        resolved_location = location or get_location()
        if not resolved_location:
            raise ValueError("No location provided and no active location selected.")
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": f"{name}-nsg"}

        rule_args = [
            azure_native.network.SecurityRuleArgs(
                name=r.name,
                priority=r.priority,
                direction=r.direction,
                access=r.access,
                protocol=r.protocol,
                source_address_prefix=r.source_address_prefix,
                source_port_range=r.source_port_range,
                destination_address_prefix=r.destination_address_prefix,
                destination_port_range=r.destination_port_range,
                description=r.description,
            )
            for r in security_rules
        ]

        kwargs = {
            "resource_group_name": resource_group_name,
            "network_security_group_name": f"{name}-nsg",
            "security_rules": rule_args,
            "tags": base_tags,
            "location": resolved_location
        }

        nsg = azure_native.network.NetworkSecurityGroup(f"{name}-nsg", **kwargs)

        pulumi.export("nsg_id", nsg.id)
        pulumi.export("nsg_name", nsg.name)
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("name", name)
        pulumi.export("nsg_location", location)
        pulumi.export("tags", nsg.tags)
        pulumi.export("rule_count", len(security_rules))
        pulumi.export("security_rules", [
            {
                "name": r.name,
                "priority": r.priority,
                "direction": r.direction,
                "access": r.access,
                "protocol": r.protocol,
                "source_address_prefix": r.source_address_prefix,
                "source_port_range": r.source_port_range,
                "destination_address_prefix": r.destination_address_prefix,
                "destination_port_range": r.destination_port_range,
                "description": r.description,
            }
            for r in security_rules
        ])

    return program
