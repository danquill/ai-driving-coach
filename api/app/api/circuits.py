from __future__ import annotations

import json as _json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/circuits", tags=["circuits"])


class CircuitSectorResponse(BaseModel):
    id: UUID
    sector_number: int
    trigger_lat: float
    trigger_lon: float
    trigger_heading_deg: float | None


class CircuitCornerResponse(BaseModel):
    id: UUID
    corner_number: int
    name: Optional[str]
    distance_m: float
    lat: float
    lon: float


class CircuitCornerCreate(BaseModel):
    corner_number: int
    name: Optional[str] = None
    distance_m: float
    lat: float
    lon: float


class CircuitCornerUpdate(BaseModel):
    corner_number: Optional[int] = None
    name: Optional[str] = None
    distance_m: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class CircuitResponse(BaseModel):
    id: UUID
    name: str
    country: str | None
    timezone: str
    start_finish_lat: float | None
    start_finish_lon: float | None
    start_finish_heading_deg: float | None
    geofence_radius_m: float | None
    track_length_m: float | None
    geometry: Optional[dict] = None
    sectors: list[CircuitSectorResponse] = []
    corners: list[CircuitCornerResponse] = []


async def _fetch_circuit(circuit_id: str, db) -> CircuitResponse:
    c = await db.fetchrow(
        """
        SELECT id, name, country, timezone,
               start_finish_lat, start_finish_lon,
               start_finish_heading_deg, geofence_radius_m, track_length_m,
               ST_AsGeoJSON(geometry)::text AS geometry_json
        FROM circuits WHERE id = $1
        """,
        circuit_id,
    )
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

    sectors = await db.fetch(
        """
        SELECT id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg
        FROM circuit_sectors WHERE circuit_id = $1 ORDER BY sector_number
        """,
        circuit_id,
    )
    corners = await db.fetch(
        """
        SELECT id, corner_number, name, distance_m, lat, lon
        FROM circuit_corners WHERE circuit_id = $1 ORDER BY corner_number
        """,
        circuit_id,
    )
    c_dict = dict(c)
    geom_json = c_dict.pop("geometry_json", None)
    geometry = _json.loads(geom_json) if geom_json else None
    return CircuitResponse(
        **c_dict,
        geometry=geometry,
        sectors=[CircuitSectorResponse(**dict(s)) for s in sectors],
        corners=[CircuitCornerResponse(**dict(cn)) for cn in corners],
    )


@router.get("/", response_model=list[CircuitResponse])
async def list_circuits(db=Depends(get_db)):
    """List all circuits (public — no auth required)."""
    circuits = await db.fetch(
        "SELECT id, name, country, timezone, start_finish_lat, start_finish_lon, "
        "start_finish_heading_deg, geofence_radius_m, track_length_m, "
        "ST_AsGeoJSON(geometry)::text AS geometry_json FROM circuits ORDER BY name"
    )
    result = []
    for c in circuits:
        sectors = await db.fetch(
            "SELECT id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg "
            "FROM circuit_sectors WHERE circuit_id = $1 ORDER BY sector_number",
            c["id"],
        )
        corners = await db.fetch(
            "SELECT id, corner_number, name, distance_m, lat, lon "
            "FROM circuit_corners WHERE circuit_id = $1 ORDER BY corner_number",
            c["id"],
        )
        c_dict = dict(c)
        geom_json = c_dict.pop("geometry_json", None)
        geometry = _json.loads(geom_json) if geom_json else None
        result.append(CircuitResponse(
            **c_dict,
            geometry=geometry,
            sectors=[CircuitSectorResponse(**dict(s)) for s in sectors],
            corners=[CircuitCornerResponse(**dict(cn)) for cn in corners],
        ))
    return result


@router.get("/{circuit_id}", response_model=CircuitResponse)
async def get_circuit(circuit_id: str, db=Depends(get_db)):
    """Get a single circuit by ID."""
    return await _fetch_circuit(circuit_id, db)


# ─── Circuit CRUD (admin) ─────────────────────────────────────────────────────

class CircuitCreate(BaseModel):
    name: str
    country: Optional[str] = None
    timezone: str = "UTC"
    track_length_m: Optional[float] = None


@router.post("/", response_model=CircuitResponse, status_code=201)
async def create_circuit(
    body: CircuitCreate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Create a new circuit (admin only)."""
    row = await db.fetchrow(
        """
        INSERT INTO circuits (name, country, timezone, track_length_m)
        VALUES ($1, $2, $3, $4)
        RETURNING id, name, country, timezone,
                  start_finish_lat, start_finish_lon,
                  start_finish_heading_deg, geofence_radius_m, track_length_m,
                  ST_AsGeoJSON(geometry)::text AS geometry_json
        """,
        body.name, body.country, body.timezone, body.track_length_m,
    )
    c_dict = dict(row)
    geom_json = c_dict.pop("geometry_json", None)
    return CircuitResponse(**c_dict, geometry=_json.loads(geom_json) if geom_json else None)


@router.delete("/{circuit_id}", status_code=204)
async def delete_circuit(
    circuit_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Delete a circuit and all associated data (admin only)."""
    deleted = await db.execute("DELETE FROM circuits WHERE id = $1", circuit_id)
    if deleted == "DELETE 0":
        raise HTTPException(status_code=404, detail="Circuit not found")


# ─── Corner admin endpoints ────────────────────────────────────────────────────

@router.post("/{circuit_id}/corners", response_model=CircuitCornerResponse, status_code=201)
async def create_corner(
    circuit_id: str,
    body: CircuitCornerCreate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Add a corner to a circuit (admin only)."""
    # Ensure circuit exists
    exists = await db.fetchval("SELECT id FROM circuits WHERE id = $1", circuit_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Circuit not found")

    row = await db.fetchrow(
        """
        INSERT INTO circuit_corners (circuit_id, corner_number, name, distance_m, lat, lon)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, corner_number, name, distance_m, lat, lon
        """,
        circuit_id, body.corner_number, body.name, body.distance_m, body.lat, body.lon,
    )
    return CircuitCornerResponse(**dict(row))


@router.patch("/{circuit_id}/corners/{corner_id}", response_model=CircuitCornerResponse)
async def update_corner(
    circuit_id: str,
    corner_id: str,
    body: CircuitCornerUpdate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Update a corner (admin only)."""
    existing = await db.fetchrow(
        "SELECT id, corner_number, name, distance_m, lat, lon "
        "FROM circuit_corners WHERE id = $1 AND circuit_id = $2",
        corner_id, circuit_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Corner not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return CircuitCornerResponse(**dict(existing))

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE circuit_corners SET {set_clauses} WHERE id = $1 "
        f"RETURNING id, corner_number, name, distance_m, lat, lon",
        corner_id, *values,
    )
    return CircuitCornerResponse(**dict(row))


@router.delete("/{circuit_id}/corners/{corner_id}", status_code=204)
async def delete_corner(
    circuit_id: str,
    corner_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Delete a corner (admin only)."""
    deleted = await db.execute(
        "DELETE FROM circuit_corners WHERE id = $1 AND circuit_id = $2",
        corner_id, circuit_id,
    )
    if deleted == "DELETE 0":
        raise HTTPException(status_code=404, detail="Corner not found")


# ─── Sessions with telemetry for a circuit (admin helper) ────────────────────

class CircuitSessionSummary(BaseModel):
    session_id: str
    session_name: Optional[str]
    session_date: Optional[str]
    lap_numbers: list[int]


@router.get("/{circuit_id}/sessions", response_model=list[CircuitSessionSummary])
async def list_sessions_for_circuit(
    circuit_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """List sessions that have telemetry for this circuit (admin only)."""
    rows = await db.fetch(
        """
        SELECT s.id, s.name, s.session_date::text,
               array_agg(DISTINCT t.lap_number ORDER BY t.lap_number)
                 FILTER (WHERE t.lap_number IS NOT NULL) AS lap_numbers
        FROM sessions s
        JOIN telemetry_samples t ON t.session_id = s.id
        WHERE s.circuit_id = $1
          AND t.lat IS NOT NULL AND t.lon IS NOT NULL
        GROUP BY s.id, s.name, s.session_date
        ORDER BY s.session_date DESC NULLS LAST, s.created_at DESC
        """,
        circuit_id,
    )
    return [
        CircuitSessionSummary(
            session_id=str(r["id"]),
            session_name=r["name"],
            session_date=r["session_date"],
            lap_numbers=list(r["lap_numbers"]),
        )
        for r in rows
    ]


# ─── Geometry import ──────────────────────────────────────────────────────────

class GeometryImportRequest(BaseModel):
    session_id: str
    lap_number: int


class GeometryImportResponse(BaseModel):
    point_count: int
    track_length_m: float


@router.post("/{circuit_id}/geometry", response_model=GeometryImportResponse)
async def import_geometry_from_lap(
    circuit_id: str,
    body: GeometryImportRequest,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Import circuit geometry from a lap's GPS telemetry (admin only)."""
    exists = await db.fetchval("SELECT id FROM circuits WHERE id = $1", circuit_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Circuit not found")

    rows = await db.fetch(
        """
        SELECT lat, lon, distance_m, heading_deg
        FROM telemetry_samples
        WHERE session_id = $1 AND lap_number = $2
          AND lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY time
        """,
        body.session_id, body.lap_number,
    )
    if len(rows) < 2:
        raise HTTPException(status_code=422, detail="Not enough GPS points in that lap")

    # Build WKT LineString
    coords_wkt = ", ".join(f"{r['lon']} {r['lat']}" for r in rows)
    wkt = f"LINESTRING({coords_wkt})"

    # Compute track length from max distance_m (lap-relative not guaranteed; use diff)
    distances = [r["distance_m"] for r in rows if r["distance_m"] is not None]
    track_length_m = (max(distances) - min(distances)) if len(distances) >= 2 else 0.0

    # First point of the lap is the start/finish line crossing
    sf_lat = float(rows[0]["lat"])
    sf_lon = float(rows[0]["lon"])
    sf_heading = float(rows[0]["heading_deg"]) if rows[0]["heading_deg"] is not None else None

    await db.execute(
        """
        UPDATE circuits
        SET geometry = ST_GeomFromText($1, 4326),
            track_length_m = $2,
            start_finish_lat = $3,
            start_finish_lon = $4,
            start_finish_heading_deg = COALESCE($5, start_finish_heading_deg)
        WHERE id = $6
        """,
        wkt, round(track_length_m, 2), sf_lat, sf_lon, sf_heading, circuit_id,
    )

    return GeometryImportResponse(point_count=len(rows), track_length_m=round(track_length_m, 2))


# ─── Sector admin endpoints ────────────────────────────────────────────────────

class CircuitSectorCreate(BaseModel):
    sector_number: int
    trigger_lat: float
    trigger_lon: float
    trigger_heading_deg: Optional[float] = None


class CircuitSectorUpdate(BaseModel):
    sector_number: Optional[int] = None
    trigger_lat: Optional[float] = None
    trigger_lon: Optional[float] = None
    trigger_heading_deg: Optional[float] = None


@router.post("/{circuit_id}/sectors", response_model=CircuitSectorResponse, status_code=201)
async def create_sector(
    circuit_id: str,
    body: CircuitSectorCreate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Add a sector trigger to a circuit (admin only)."""
    exists = await db.fetchval("SELECT id FROM circuits WHERE id = $1", circuit_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Circuit not found")

    row = await db.fetchrow(
        """
        INSERT INTO circuit_sectors (circuit_id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (circuit_id, sector_number) DO UPDATE
            SET trigger_lat = EXCLUDED.trigger_lat,
                trigger_lon = EXCLUDED.trigger_lon,
                trigger_heading_deg = EXCLUDED.trigger_heading_deg
        RETURNING id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg
        """,
        circuit_id, body.sector_number, body.trigger_lat, body.trigger_lon, body.trigger_heading_deg,
    )
    return CircuitSectorResponse(**dict(row))


@router.patch("/{circuit_id}/sectors/{sector_id}", response_model=CircuitSectorResponse)
async def update_sector(
    circuit_id: str,
    sector_id: str,
    body: CircuitSectorUpdate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Update a sector trigger (admin only)."""
    existing = await db.fetchrow(
        "SELECT id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg "
        "FROM circuit_sectors WHERE id = $1 AND circuit_id = $2",
        sector_id, circuit_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Sector not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return CircuitSectorResponse(**dict(existing))

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE circuit_sectors SET {set_clauses} WHERE id = $1 "
        f"RETURNING id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg",
        sector_id, *values,
    )
    return CircuitSectorResponse(**dict(row))


@router.delete("/{circuit_id}/sectors/{sector_id}", status_code=204)
async def delete_sector(
    circuit_id: str,
    sector_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Delete a sector trigger (admin only)."""
    deleted = await db.execute(
        "DELETE FROM circuit_sectors WHERE id = $1 AND circuit_id = $2",
        sector_id, circuit_id,
    )
    if deleted == "DELETE 0":
        raise HTTPException(status_code=404, detail="Sector not found")
