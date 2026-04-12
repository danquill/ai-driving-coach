#!/usr/bin/env python3
"""Export all track data (circuits, corners, sectors) to data/tracks.json.

Usage (from project root):
    docker compose run --rm -v "$(pwd)/data:/data" api python /app/scripts/export_tracks.py

Output: /data/tracks.json (mounted from ./data on the host)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg


async def main() -> None:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://track:@db:5432/trackdb",
    ).replace("postgresql+asyncpg://", "postgresql://")

    # Resolve DB password from Docker secret (replaces DOCKER-SECRET placeholder)
    password_file = os.environ.get("DB_PASSWORD_FILE", "/run/secrets/db_password")
    secret_path = Path(password_file)
    if secret_path.exists():
        password = secret_path.read_text().strip()
        db_url = db_url.replace("DOCKER-SECRET", password).replace(":@", f":{password}@")

    conn = await asyncpg.connect(db_url)

    try:
        # ── Circuits ──────────────────────────────────────────────────────────
        circuits = await conn.fetch("""
            SELECT
                id::text,
                name,
                country,
                timezone,
                start_finish_lat,
                start_finish_lon,
                start_finish_heading_deg::float,
                geofence_radius_m::float,
                track_length_m::float,
                ST_AsGeoJSON(geometry)::text AS geometry_geojson
            FROM circuits
            ORDER BY name
        """)

        # ── Corners ───────────────────────────────────────────────────────────
        corners = await conn.fetch("""
            SELECT
                id::text,
                circuit_id::text,
                corner_number,
                name,
                distance_m::float,
                lat,
                lon
            FROM circuit_corners
            ORDER BY circuit_id, corner_number
        """)

        # ── Sectors ───────────────────────────────────────────────────────────
        sectors = await conn.fetch("""
            SELECT
                id::text,
                circuit_id::text,
                sector_number,
                trigger_lat,
                trigger_lon,
                trigger_heading_deg::float
            FROM circuit_sectors
            ORDER BY circuit_id, sector_number
        """)

    finally:
        await conn.close()

    # Group corners and sectors by circuit_id
    corners_by_circuit: dict[str, list] = {}
    for row in corners:
        cid = row["circuit_id"]
        corners_by_circuit.setdefault(cid, []).append({
            "id": row["id"],
            "corner_number": row["corner_number"],
            "name": row["name"],
            "distance_m": row["distance_m"],
            "lat": row["lat"],
            "lon": row["lon"],
        })

    sectors_by_circuit: dict[str, list] = {}
    for row in sectors:
        cid = row["circuit_id"]
        sectors_by_circuit.setdefault(cid, []).append({
            "id": row["id"],
            "sector_number": row["sector_number"],
            "trigger_lat": row["trigger_lat"],
            "trigger_lon": row["trigger_lon"],
            "trigger_heading_deg": row["trigger_heading_deg"],
        })

    # Build final structure
    output = []
    for c in circuits:
        cid = c["id"]
        entry: dict = {
            "id": cid,
            "name": c["name"],
            "country": c["country"],
            "timezone": c["timezone"],
            "start_finish_lat": c["start_finish_lat"],
            "start_finish_lon": c["start_finish_lon"],
            "start_finish_heading_deg": c["start_finish_heading_deg"],
            "geofence_radius_m": c["geofence_radius_m"],
            "track_length_m": c["track_length_m"],
            "geometry": json.loads(c["geometry_geojson"]) if c["geometry_geojson"] else None,
            "corners": corners_by_circuit.get(cid, []),
            "sectors": sectors_by_circuit.get(cid, []),
        }
        output.append(entry)

    out_path = Path("/data/tracks.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))

    n_circuits = len(output)
    n_corners = sum(len(c["corners"]) for c in output)
    n_sectors = sum(len(c["sectors"]) for c in output)
    print(f"Exported {n_circuits} circuits, {n_corners} corners, {n_sectors} sectors → {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
