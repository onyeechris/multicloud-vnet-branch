from typing import Dict, Optional
import pulumi
import pulumi_azure_native as azure_native
import pulumi_tls as tls
from app.utils.location_state import get_location


def create_key_pair_program(
    name: str,
    resource_group_name: str,
    location: Optional[str],
    tags: Dict[str, str],
):
    def program():
        base_tags = {"ManagedBy": "Pulumi", **tags, "Name": name}

        generated = tls.PrivateKey(f"{name}-tls-key", algorithm="RSA", rsa_bits=4096)

        client_cfg = azure_native.authorization.get_client_config_output()

        vault_kwargs = {
            "resource_group_name": resource_group_name,
            "properties": azure_native.keyvault.VaultPropertiesArgs(
                tenant_id=client_cfg.tenant_id,
                sku=azure_native.keyvault.SkuArgs(
                    family=azure_native.keyvault.SkuFamily.A,
                    name=azure_native.keyvault.SkuName.STANDARD,
                ),
                access_policies=[
                    azure_native.keyvault.AccessPolicyEntryArgs(
                        tenant_id=client_cfg.tenant_id,
                        object_id=client_cfg.object_id,
                        permissions=azure_native.keyvault.PermissionsArgs(
                            secrets=["get", "list", "set", "delete", "recover", "purge"],
                        ),
                    ),
                ],
                enable_soft_delete=True,
                soft_delete_retention_in_days=7,
                enable_purge_protection=None,
            ),
            "tags": base_tags,
        }
        if location:
            vault_kwargs["location"] = location

        # Store the private key in Azure Key Vault so it is maintained entirely in Azure,
        # mirroring console behaviour where the key material never leaves the cloud.
        kv = azure_native.keyvault.Vault(f"{name}-kv", **vault_kwargs)

        secret = azure_native.keyvault.Secret(
            f"{name}-private-key-secret",
            resource_group_name=resource_group_name,
            vault_name=kv.name,
            secret_name=f"{name}-private-key",
            properties=azure_native.keyvault.SecretPropertiesArgs(
                value=generated.private_key_pem,
            ),
            tags=base_tags,
        )

        ssh_kwargs = {
            "resource_group_name": resource_group_name,
            "ssh_public_key_name": name,
            "public_key": generated.public_key_openssh,
            "tags": base_tags,
        }
        if location:
            ssh_kwargs["location"] = location
        ssh_pub = azure_native.compute.SshPublicKey(f"{name}-ssh-public-key", **ssh_kwargs)

        pulumi.export("key_name", name)
        pulumi.export("ssh_public_key_id", ssh_pub.id)
        pulumi.export("public_key_openssh", generated.public_key_openssh)
        pulumi.export("key_vault_name", kv.name)
        pulumi.export("key_vault_uri", kv.properties.vault_uri)
        pulumi.export("private_key_secret_name", secret.name)
        pulumi.export("private_key_secret_id", secret.id)
        pulumi.export("resource_group_name", resource_group_name)
        pulumi.export("name", name)

    return program
