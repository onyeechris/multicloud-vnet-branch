from typing import Dict, Optional
import pulumi
import pulumi_azure_native as azure_native
from app.utils.location_state import get_location

from app.models.virtual_machine import ImageReference


def create_virtual_machine_program(
    name: str,
    resource_group_name: str,
    subnet_id: str,
    vm_size: str,
    admin_username: str,
    admin_password: Optional[str],
    ssh_public_key: Optional[str],
    key_pair_stack: Optional[str],
    create_public_ip: bool,
    nsg_id: Optional[str],
    image: ImageReference,
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        resolved_location = location or get_location()
        if not resolved_location:
            raise ValueError("No location provided and no active location selected.")
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": name}

        public_ip_id = None
        if create_public_ip:
            pip_kwargs = {
                "resource_group_name": resource_group_name,
                "public_ip_address_name": f"{name}-pip",
                "public_ip_allocation_method": "Static",
                "sku": azure_native.network.PublicIPAddressSkuArgs(name="Standard"),
                "location": resolved_location,
                "tags": {**base_tags, "Name": f"{name}-pip"},
            }
            pip = azure_native.network.PublicIPAddress(
                f"{name}-pip",
                **pip_kwargs
            )
            public_ip_id = pip.id
            pulumi.export("public_ip", pip.ip_address)

        ip_config_kwargs = {
            "name": f"{name}-ipcfg",
            "subnet": azure_native.network.SubnetArgs(id=subnet_id),
            "private_ip_allocation_method": "Dynamic",
        }
        if public_ip_id is not None:
            ip_config_kwargs["public_ip_address"] = azure_native.network.PublicIPAddressArgs(
                id=public_ip_id,
            )

        nic_kwargs = {
            "resource_group_name": resource_group_name,
            "network_interface_name": f"{name}-nic",
            "ip_configurations": [
                azure_native.network.NetworkInterfaceIPConfigurationArgs(**ip_config_kwargs),
            ],
            "location": resolved_location,
            "tags": {**base_tags, "Name": f"{name}-nic"},
        }
        if nsg_id:
            nic_kwargs["network_security_group"] = azure_native.network.NetworkSecurityGroupArgs(
                id=nsg_id,
            )
        nic = azure_native.network.NetworkInterface(f"{name}-nic", **nic_kwargs)

        os_profile_kwargs = {
            "computer_name": name[:15],
            "admin_username": admin_username,
        }
        if ssh_public_key:
            os_profile_kwargs["linux_configuration"] = azure_native.compute.LinuxConfigurationArgs(
                disable_password_authentication=True,
                ssh=azure_native.compute.SshConfigurationArgs(
                    public_keys=[
                        azure_native.compute.SshPublicKeyArgs(
                            path=f"/home/{admin_username}/.ssh/authorized_keys",
                            key_data=ssh_public_key,
                        ),
                    ],
                ),
            )
            auth_method = "ssh-key"
        else:
            os_profile_kwargs["admin_password"] = admin_password
            auth_method = "password"

        vm_kwargs = {
            "resource_group_name": resource_group_name,
            "vm_name": name,
            "hardware_profile": azure_native.compute.HardwareProfileArgs(vm_size=vm_size),
            "os_profile": azure_native.compute.OSProfileArgs(**os_profile_kwargs),
            "location": resolved_location,
            "network_profile": azure_native.compute.NetworkProfileArgs(
                network_interfaces=[
                    azure_native.compute.NetworkInterfaceReferenceArgs(
                        id=nic.id,
                        primary=True,
                    ),
                ],
            ),
            "storage_profile": azure_native.compute.StorageProfileArgs(
                image_reference=azure_native.compute.ImageReferenceArgs(
                    publisher=image.publisher,
                    offer=image.offer,
                    sku=image.sku,
                    version=image.version,
                ),
                os_disk=azure_native.compute.OSDiskArgs(
                    create_option="FromImage",
                    name=f"{name}-osdisk",
                    delete_option="Delete",
                ),
            ),
            "tags": base_tags,
        }

        vm = azure_native.compute.VirtualMachine(name, **vm_kwargs)

        pulumi.export("vm_id", vm.id)
        pulumi.export("vm_name", vm.name)
        pulumi.export("vm_size", vm_size)
        pulumi.export("admin_username", admin_username)
        pulumi.export("auth_method", auth_method)
        pulumi.export("key_pair_stack", key_pair_stack or "")
        pulumi.export("nic_id", nic.id)
        pulumi.export("subnet_id", subnet_id)
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("create_public_ip", create_public_ip)
        pulumi.export("nsg_id", nsg_id)
        private_ip = nic.ip_configurations.apply(
            lambda ip_configs: ip_configs[0].private_ip_address if ip_configs else None
        )
        pulumi.export("private_ip", private_ip)
        pulumi.export("image", {
            "publisher": image.publisher,
            "offer": image.offer,
            "sku": image.sku,
            "version": image.version,
        })
        pulumi.export("name", name)
        pulumi.export("vm_location", location)

    return program
