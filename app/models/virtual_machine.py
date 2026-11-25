from pydantic import BaseModel, Field, model_validator
from typing import Dict, Optional


class ImageReference(BaseModel):
    publisher: str = "Canonical"
    offer: str = "0001-com-ubuntu-server-jammy"
    sku: str = "22_04-lts-gen2"
    version: str = "latest"


class VirtualMachineRequest(BaseModel):
    stack: str = Field(..., description="Pulumi stack name")
    location: Optional[str] = Field(None, description="Azure location — omit to use the pre-selected location")
    name: str = Field(..., description="Resource name prefix")
    resource_group_name: str = Field(..., description="Target resource group name")
    subnet_id: str = Field(..., description="Subnet ID to place the VM's NIC in")
    vm_size: str = Field("Standard_B1s", description="VM size, e.g. Standard_B1s")
    admin_username: str = Field(..., description="Admin username")
    admin_password: Optional[str] = Field(
        None, description="Admin password — provide this OR an SSH key (key_pair_stack / ssh_public_key)"
    )
    ssh_public_key: Optional[str] = Field(
        None, description="Raw SSH public key contents — alternative to admin_password / key_pair_stack"
    )
    key_pair_stack: Optional[str] = Field(
        None, description="Pulumi stack name that exported public_key_openssh — alternative to admin_password / ssh_public_key"
    )
    create_public_ip: bool = Field(True, description="Auto-create a Public IP for the VM")
    nsg_id: Optional[str] = Field(None, description="Optional NSG resource ID to attach to the NIC — alternative to nsg_stack")
    nsg_stack: Optional[str] = Field(
        None,
        description="Pulumi stack name that exported nsg_id — alternative to nsg_id (cannot set both)",
    )
    image: ImageReference = Field(default_factory=ImageReference)
    tags: Dict[str, str] = {}

    @model_validator(mode="after")
    def validate_credentials(self) -> "VirtualMachineRequest":
        provided = [
            bool(self.admin_password),
            bool(self.ssh_public_key),
            bool(self.key_pair_stack),
        ]
        if not any(provided):
            raise ValueError(
                "Provide exactly one auth method: admin_password, ssh_public_key, or key_pair_stack"
            )
        if sum(provided) > 1:
            raise ValueError(
                "Only one auth method may be set at a time: admin_password, ssh_public_key, or key_pair_stack"
            )
        if self.nsg_id and self.nsg_stack:
            raise ValueError("Set only one of nsg_id or nsg_stack, not both")
        return self


class VirtualMachinePatchRequest(BaseModel):
    stack: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    resource_group_name: Optional[str] = None
    subnet_id: Optional[str] = None
    vm_size: Optional[str] = None
    admin_username: Optional[str] = None
    admin_password: Optional[str] = None
    ssh_public_key: Optional[str] = None
    key_pair_stack: Optional[str] = None
    create_public_ip: Optional[bool] = None
    nsg_id: Optional[str] = None
    nsg_stack: Optional[str] = None
    # image: Optional[ImageReference] = None
    tags: Optional[Dict[str, str]] = None
