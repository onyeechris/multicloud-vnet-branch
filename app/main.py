import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI

from app.routes.location import router as location_router
from app.routes.resource_group import router as resource_group_router
from app.routes.vnet import router as vnet_router
from app.routes.subnet import router as subnet_router
from app.routes.nsg import router as nsg_router
from app.routes.route_table import router as route_table_router
from app.routes.route import router as route_router
from app.routes.nat_gateway import router as nat_gateway_router
from app.routes.key_pair import router as key_pair_router
from app.routes.virtual_machine import router as virtual_machine_router
from app.routes.images import router as images_router



# Pulumi state backend — Azure Blob takes priority; fall back to Pulumi Cloud token.
_backend_url = os.getenv("PULUMI_BACKEND_URL")
_pulumi_token = os.getenv("PULUMI_ACCESS_TOKEN")

if _backend_url:
    os.environ["PULUMI_BACKEND_URL"] = _backend_url
elif _pulumi_token:
    os.environ["PULUMI_ACCESS_TOKEN"] = _pulumi_token
else:
    raise RuntimeError(
        "No Pulumi backend configured. Set either PULUMI_BACKEND_URL (azblob://) "
        "or PULUMI_ACCESS_TOKEN (Pulumi Cloud) in your .env file."
    )

# Required when using a self-hosted backend (azblob).
_passphrase = os.getenv("PULUMI_CONFIG_PASSPHRASE")
if _passphrase is None:
    raise RuntimeError(
        "PULUMI_CONFIG_PASSPHRASE is not set. Add it to your .env file. "
        "Set to empty string to disable passphrase encryption."
    )
os.environ["PULUMI_CONFIG_PASSPHRASE"] = _passphrase

app = FastAPI(
    title="MultiCloud Edge — Azure Networking Service",
    description=(
        "Microservice for provisioning Azure networking resources via the Pulumi Automation API. "
        "Each resource type (Resource Group, VNet, Subnet, NSG, Route Table, Route, NAT Gateway, "
        "Key Pair, Virtual Machine) is an independent Pulumi stack with full CRUD endpoints."
    ),
    version="2.0.0",
)

app.include_router(location_router)
app.include_router(resource_group_router)
app.include_router(vnet_router)
app.include_router(subnet_router)
app.include_router(nsg_router)
app.include_router(route_table_router)
app.include_router(route_router)
app.include_router(nat_gateway_router)
app.include_router(key_pair_router)
app.include_router(virtual_machine_router)
app.include_router(images_router)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "SERVER IS RUNNING"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "azure-networking"}
