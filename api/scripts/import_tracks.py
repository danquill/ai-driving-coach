#!/usr/bin/env python3
"""Import track data from data/tracks.json into the database.

Performs an upsert — existing circuits (matched by id) are updated,
new ones are inserted. Corners and sectors are replaced for any circuit
that appears in the file (delete-then-insert by circuit).

Usage (from project root):
    docker compose run --rm -v "$(pwd)/data:/data" api python /app/scripts/import_tracks.py

Input: /data/tracks.json (mounted from ./data on the host)
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import asyncpg


async def main() -> None:
    in_path = Path("/data/tracks.json")
    if not in_path.exists():
        print(f"ERROR: {in_path} not found. Run export_tracks.py first.", flush=True)
        raise SystemExit(1)

    tracks = json.loads(in_path.read_text())
    print(f"Loaded {len(tracks)} circuits from {in_path}")

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://track:@db:5432/trackdb",
    ).replace("postgresql+asyncpg://", "postgresql://")

    password_file = os.environ.get("DB_PASSWORD_FILE", "/run/secrets/db_password")
    secret_path = Path(password_file)
    if secret_path.exists():
        password = secret_path.read_text().strip()
        db_url = db_url.replace("DOCKER-SECRET", password).replace(":@", f":{password}@")

    conn = await asyncpg.connect(db_url)

    try:
        async with conn.transaction():
            for circuit in tracks:
                cid = circuit["id"]

                # Build geometry SQL fragment
                geom_sql = "NULL"
                geom_val = None
                if circuit.get("geometry"):
                    geom_val = json.dumps(circuit["geometry"])

                # Upsert circuit
                if geom_val:
                    await conn.execute("""
                        INSERT INTO circuits (
                            id, name, country, timezone,
                            start_finish_lat, start_finish_lon, start_finish_heading_deg,
                            geofence_radius_m, track_length_m, geometry
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, ST_GeomFromGeoJSON($10))
                        ON CONFLICT (id) DO UPDATE SET
                            name                     = EXCLUDED.name,
                            country                  = EXCLUDED.country,
                            timezone                 = EXCLUDED.timezone,
                            start_finish_lat         = EXCLUDED.start_finish_lat,
                            start_finish_lon         = EXCLUDED.start_finish_lon,
                            start_finish_heading_deg = EXCLUDED.start_finish_heading_deg,
                            geofence_radius_m        = EXCLUDED.geofence_radius_m,
                            track_length_m           = EXCLUDED.track_length_m,
                            geometry                 = EXCLUDED.geometry
                    """,
                        uuid.UUID(cid),
                        circuit.get("name"),
                        circuit.get("country"),
                        circuit.get("timezone") or "UTC",
                        circuit.get("start_finish_lat"),
                        circuit.get("start_finish_lon"),
                        circuit.get("start_finish_heading_deg"),
                        circuit.get("geofence_radius_m"),
                        circuit.get("track_length_m"),
                        geom_val,
                    )
                else:
                    await conn.execute("""
                        INSERT INTO circuits (
                            id, name, country, timezone,
                            start_finish_lat, start_finish_lon, start_finish_heading_deg,
                            geofence_radius_m, track_length_m
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        ON CONFLICT (id) DO UPDATE SET
                            name                     = EXCLUDED.name,
                            country                  = EXCLUDED.country,
                            timezone                 = EXCLUDED.timezone,
                            start_finish_lat         = EXCLUDED.start_finish_lat,
                            start_finish_lon         = EXCLUDED.start_finish_lon,
                            start_finish_heading_deg = EXCLUDED.start_finish_heading_deg,
                            geofence_radius_m        = EXCLUDED.geofence_radius_m,
                            track_length_m           = EXCLUDED.track_length_m
                    """,
                        uuid.UUID(cid),
                        circuit.get("name"),
                        circuit.get("country"),
                        circuit.get("timezone") or "UTC",
                        circuit.get("start_finish_lat"),
                        circuit.get("start_finish_lon"),
                        circuit.get("start_finish_heading_deg"),
                        circuit.get("geofence_radius_m"),
                        circuit.get("track_length_m"),
                    )

                # Replace corners for this circuit
                await conn.execute(
                    "DELETE FROM circuit_corners WHERE circuit_id = $1",
                    uuid.UUID(cid),
                )
                for corner in circuit.get("corners", []):
                    await conn.execute("""
                        INSERT INTO circuit_corners
                            (id, circuit_id, corner_number, name, distance_m, lat, lon)
                        VALUES ($1,$2,$3,$4,$5,$6,$7)
                    """,
                        uuid.UUID(corner["id"]),
                        uuid.UUID(cid),
                        corner["corner_number"],
                        corner.get("name"),
                        corner["distance_m"],
                        corner["lat"],
                        corner["lon"],
                    )

                # Replace sectors for this circuit
                await conn.execute(
                    "DELETE FROM circuit_sectors WHERE circuit_id = $1",
                    uuid.UUID(cid),
                )
                for sector in circuit.get("sectors", []):
                    await conn.execute("""
                        INSERT INTO circuit_sectors
                            (id, circuit_id, sector_number, trigger_lat, trigger_lon, trigger_heading_deg)
                        VALUES ($1,$2,$3,$4,$5,$6)
                    """,
                        uuid.UUID(sector["id"]),
                        uuid.UUID(cid),
                        sector["sector_number"],
                        sector["trigger_lat"],
                        sector["trigger_lon"],
                        sector.get("trigger_heading_deg"),
                    )

                n_c = len(circuit.get("corners", []))
                n_s = len(circuit.get("sectors", []))
                print(f"  ✓ {circuit['name']} ({n_c} corners, {n_s} sectors)")

    finally:
        await conn.close()

    print(f"Import complete — {len(tracks)} circuits upserted.")


if __name__ == "__main__":
    asyncio.run(main())
