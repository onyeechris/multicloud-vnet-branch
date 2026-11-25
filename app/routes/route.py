from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models.common import StackResponse
from app.models.route import RouteRequest, RoutePatchRequest, RouteEntry
from app.pulumi_programs.route import create_route_program
from app.utils.stack import stack_up_safe, stack_outputs, stack_destroy, stack_location, stack_list, stack_exists
from app.utils.location_state import get_location

router = APIRouter(prefix="/route", tags=["Route"])


def _resolve_route_table_name(route_table_name: Optional[str], route_table_stack: Optional[str]) -> str:
    """Return the final route_table_name, resolving from a stack name if needed."""
    if route_table_name and route_table_stack:
        raise HTTPException(status_code=400, detail="Set only one of route_table_name or route_table_stack, not both")
    if route_table_name:
        return route_table_name
    if not route_table_stack:
        raise HTTPException(status_code=422, detail="Provide route_table_name or route_table_stack")
    try:
        outputs = stack_outputs(route_table_stack)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not resolve route table stack '{route_table_stack}': {exc}")
    resolved = outputs.get("route_table_name")
    if not resolved:
        raise HTTPException(status_code=404, detail=f"route_table_name not found in stack '{route_table_stack}'")
    return resolved


@router.get("", response_model=List[StackResponse])
def list_routes():
    """List all Route stacks."""
    try:
        all_stacks = stack_list()
        return [
            StackResponse(status="ok", stack=s["name"], outputs=s["outputs"])
            for s in all_stacks if "route_ids" in s["outputs"]
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=StackResponse, status_code=201)
def create_route(req: RouteRequest):
    """Create one or more routes inside an existing Route Table."""
    if stack_exists(req.stack):
        raise HTTPException(status_code=409, detail="Route stack already exist")
    location = req.location or get_location()
    if not location:
        raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
    try:
        route_table_name = _resolve_route_table_name(req.route_table_name, req.route_table_stack)
        program = create_route_program(
            req.name, req.resource_group_name, route_table_name, req.routes, location, req.tags
        )
        outputs = stack_up_safe(req.stack, location, program)
        return StackResponse(status="created", stack=req.stack, outputs=outputs)
    except Exception as exc:
        if stack_exists(req.stack):
            try:
                stack_destroy(req.stack)
            except Exception as exc2:
                raise HTTPException(
                    status_code=500,
                    detail=f"Original error: {exc}. Also failed to cleanup: {exc2}. Manually check stack {req.stack}"
                )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{stack_name}", response_model=StackResponse)
def get_route(stack_name: str):
    """Fetch outputs of an existing Route stack."""
    try:
        outputs = stack_outputs(stack_name)
        return StackResponse(status="ok", stack=stack_name, outputs=outputs)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# @router.put("/{stack_name}", response_model=StackResponse)
# def update_route(stack_name: str, req: RouteRequest):
#     """Update an existing Route stack."""
#     if req.stack != stack_name:
#         raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
#     location = req.location or get_location()
#     if not location:
#         raise HTTPException(status_code=422, detail="No location provided and no active location selected. Call POST /location/{location} first.")
#     try:
#         route_table_name = _resolve_route_table_name(req.route_table_name, req.route_table_stack)
#         program = create_route_program(
#             req.name, req.resource_group_name, route_table_name, req.routes, location, req.tags
#         )
#         outputs = stack_up_safe(stack_name, location, program)
#         return StackResponse(status="updated", stack=stack_name, outputs=outputs)
#     except HTTPException:
#         raise
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{stack_name}", response_model=StackResponse)
def patch_route(stack_name: str, req: RoutePatchRequest):
    """Partially update a Route stack — only send the fields you want to change."""
    if req.stack is not None and req.stack != stack_name:
        raise HTTPException(status_code=400, detail="YOU CAN NOT CHANGE STACK NAME")
    try:
        current = stack_outputs(stack_name)
        location = current.get("route_location")
        name = req.name if req.name is not None else current.get("name", stack_name)
        resource_group_name = current.get("resource_group_name")
        if resource_group_name is None:
            raise HTTPException(status_code=422, detail="resource_group_name could not be resolved from stack outputs; provide it in the request body")

        if req.route_table_name is not None or req.route_table_stack is not None:
            route_table_name = _resolve_route_table_name(req.route_table_name, req.route_table_stack)
        else:
            route_table_name = current.get("route_table_name")
            if not route_table_name:
                raise HTTPException(status_code=422, detail="route_table_name could not be resolved from stack outputs; provide route_table_name or route_table_stack")

        if req.routes is not None:
            routes = req.routes
        else:
            raw = current.get("route_entries")
            if not raw:
                raise HTTPException(status_code=422, detail="routes could not be resolved from stack outputs; provide them in the request body")
            routes = [RouteEntry(**r) for r in raw]
        tags = req.tags if req.tags is not None else current.get("tags", {})
        program = create_route_program(
            name, resource_group_name, route_table_name, routes, location, tags
        )
        outputs = stack_up_safe(stack_name, location, program)
        return StackResponse(status="updated", stack=stack_name, outputs=outputs)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{stack_name}")
def delete_route(stack_name: str):
    """Destroy the Route stack."""
    try:
        stack_destroy(stack_name)
        return {"status": "deleted", "stack": stack_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
