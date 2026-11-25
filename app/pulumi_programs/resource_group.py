from typing import Dict, Optional
import pulumi
import pulumi_azure_native as azure_native


def create_resource_group_program(
    name: str,
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": name}
        kwargs = {
            "resource_group_name": name,
            "tags": base_tags,
        }
        if location:
            kwargs["location"] = location
        rg = azure_native.resources.ResourceGroup(f"{name}-rg", **kwargs)
        pulumi.export("resource_group_id", rg.id)
        pulumi.export("resource_group_name", rg.name)
        pulumi.export("location", rg.location)
        pulumi.export("name", name)

    return program
