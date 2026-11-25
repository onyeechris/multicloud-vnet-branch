from fastapi import APIRouter, HTTPException

from app.utils.location_state import AzureLocation, get_location, set_location

router = APIRouter(prefix="/location", tags=["Location"])


@router.post("/{location}", status_code=200)
async def select_location(location: AzureLocation):
    """Pre-select the active Azure location used by all stack operations."""
    set_location(location)
    return {"active_location": location.value}


@router.get("")
async def current_location():
    """Return the currently active Azure location."""
    loc = get_location()
    if loc is None:
        raise HTTPException(status_code=404, detail="No location selected yet. Call POST /location/{location} first.")
    return {"active_location": loc}
