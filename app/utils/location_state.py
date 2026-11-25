from enum import Enum


class AzureLocation(str, Enum):
    eastus = "eastus"
    eastus2 = "eastus2"
    westus = "westus"
    westus2 = "westus2"
    centralus = "centralus"
    northeurope = "northeurope"
    westeurope = "westeurope"
    uksouth = "uksouth"


_active_location: str = AzureLocation.eastus.value


def set_location(location: AzureLocation) -> None:
    global _active_location
    _active_location = location.value


def get_location() -> str | None:
    return _active_location
