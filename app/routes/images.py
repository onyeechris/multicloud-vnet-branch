from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.models.virtual_machine import ImageReference

router = APIRouter(prefix="/images", tags=["VM Images"])


class OSType(str, Enum):
    Linux = "Linux"
    Windows = "Windows"


class CuratedImage(BaseModel):
    id: str
    os: OSType
    distro: str
    image: ImageReference


# Curated list of popular Azure Marketplace images. Each entry's `image` block
# can be pasted directly into the VM create request body.
_CURATED_IMAGES: List[CuratedImage] = [
    CuratedImage(
        id="ubuntu-22-04-lts",
        os=OSType.Linux,
        distro="Ubuntu 22.04 LTS (Jammy)",
        image=ImageReference(
            publisher="Canonical",
            offer="0001-com-ubuntu-server-jammy",
            sku="22_04-lts-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="ubuntu-24-04-lts",
        os=OSType.Linux,
        distro="Ubuntu 24.04 LTS (Noble)",
        image=ImageReference(
            publisher="Canonical",
            offer="ubuntu-24_04-lts",
            sku="server-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="ubuntu-20-04-lts",
        os=OSType.Linux,
        distro="Ubuntu 20.04 LTS (Focal)",
        image=ImageReference(
            publisher="Canonical",
            offer="0001-com-ubuntu-server-focal",
            sku="20_04-lts-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="debian-12",
        os=OSType.Linux,
        distro="Debian 12 (Bookworm)",
        image=ImageReference(
            publisher="Debian",
            offer="debian-12",
            sku="12-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="debian-11",
        os=OSType.Linux,
        distro="Debian 11 (Bullseye)",
        image=ImageReference(
            publisher="Debian",
            offer="debian-11",
            sku="11-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="rhel-9",
        os=OSType.Linux,
        distro="Red Hat Enterprise Linux 9",
        image=ImageReference(
            publisher="RedHat",
            offer="RHEL",
            sku="9-lvm-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="rhel-8",
        os=OSType.Linux,
        distro="Red Hat Enterprise Linux 8",
        image=ImageReference(
            publisher="RedHat",
            offer="RHEL",
            sku="8-lvm-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="centos-stream-9",
        os=OSType.Linux,
        distro="CentOS Stream 9",
        image=ImageReference(
            publisher="OpenLogic",
            offer="CentOS",
            sku="9-stream-gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="rocky-linux-9",
        os=OSType.Linux,
        distro="Rocky Linux 9",
        image=ImageReference(
            publisher="resf",
            offer="rockylinux-x86_64",
            sku="9-base",
            version="latest",
        ),
    ),
    CuratedImage(
        id="suse-sles-15",
        os=OSType.Linux,
        distro="SUSE Linux Enterprise Server 15 SP5",
        image=ImageReference(
            publisher="SUSE",
            offer="sles-15-sp5",
            sku="gen2",
            version="latest",
        ),
    ),
    CuratedImage(
        id="windows-server-2022-datacenter",
        os=OSType.Windows,
        distro="Windows Server 2022 Datacenter",
        image=ImageReference(
            publisher="MicrosoftWindowsServer",
            offer="WindowsServer",
            sku="2022-datacenter-azure-edition",
            version="latest",
        ),
    ),
    CuratedImage(
        id="windows-server-2019-datacenter",
        os=OSType.Windows,
        distro="Windows Server 2019 Datacenter",
        image=ImageReference(
            publisher="MicrosoftWindowsServer",
            offer="WindowsServer",
            sku="2019-datacenter-gensecond",
            version="latest",
        ),
    ),
    CuratedImage(
        id="windows-11-pro-23h2",
        os=OSType.Windows,
        distro="Windows 11 Pro 23H2",
        image=ImageReference(
            publisher="MicrosoftWindowsDesktop",
            offer="windows-11",
            sku="win11-23h2-pro",
            version="latest",
        ),
    ),
]


@router.get("", response_model=List[CuratedImage])
def list_images(os: Optional[OSType] = Query(default=None, description="Filter by OS family (Linux or Windows)")):
    """List curated Azure Marketplace VM images. Use an entry's `image` block
    directly as the `image` field when creating a Virtual Machine."""
    if os is None:
        return _CURATED_IMAGES
    return [img for img in _CURATED_IMAGES if img.os == os]
