"""Vehicle CRUD endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.vehicle import CreateVehicleRequest, UpdateVehicleRequest, VehicleResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_response(row) -> VehicleResponse:
    d = dict(row)
    # DB column is 'class'; schema field is class_ with alias 'class'
    return VehicleResponse(
        id=d["id"],
        owner_id=d["owner_id"],
        make=d["make"],
        model=d["model"],
        year=d.get("year"),
        **{"class": d.get("class")},
        notes=d.get("notes"),
        created_at=d["created_at"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    body: CreateVehicleRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        """
        INSERT INTO vehicles (owner_id, make, model, year, class, notes)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        uuid.UUID(str(current_user["id"])),
        body.make,
        body.model,
        body.year,
        body.class_,
        body.notes,
    )
    return _row_to_response(row)


@router.get("/", response_model=list[VehicleResponse])
async def list_vehicles(
    skip: int = 0,
    limit: int = 50,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = await db.fetch(
        """
        SELECT * FROM vehicles
        WHERE owner_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        uuid.UUID(str(current_user["id"])),
        limit,
        skip,
    )
    return [_row_to_response(r) for r in rows]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT * FROM vehicles WHERE id = $1",
        vehicle_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _row_to_response(row)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    body: UpdateVehicleRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT * FROM vehicles WHERE id = $1",
        vehicle_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    updates = body.model_dump(exclude_none=True, by_alias=True)
    if not updates:
        return _row_to_response(row)

    set_clauses = []
    values = []
    for i, (col, val) in enumerate(updates.items(), start=2):
        set_clauses.append(f"{col} = ${i}")
        values.append(val)

    query = f"UPDATE vehicles SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
    updated = await db.fetchrow(query, vehicle_id, *values)
    return _row_to_response(updated)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT * FROM vehicles WHERE id = $1",
        vehicle_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.execute("DELETE FROM vehicles WHERE id = $1", vehicle_id)
