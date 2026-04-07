"""Seed circuit data — Summit Point Main Circuit.

Revision ID: 003
Revises: 002
Create Date: 2026-04-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels = None
depends_on = None

# =========================================================================
# Summit Point Main Circuit — Summit Point, WV, USA
# Official length: 2.000 mi (3.219 km)
# Start/finish: Main straight, heading approximately east (toward Turn 1)
#
# Layout: 10-turn circuit. S/F straight leads into a hard right at T1,
# then a flowing infield section (T2–T6), back straight (T7), sweeping
# right complex (T8–T9), and a short straight to T10 back onto S/F.
#
# Coordinates sourced from public GPS references and satellite imagery.
# Sector triggers are approximate and should be validated with real data.
# =========================================================================

CIRCUIT = {
    "id": "a6000000-0000-0000-0000-000000000006",
    "name": "Summit Point Main",
    "country": "USA",
    "timezone": "America/New_York",
    "start_finish_lat": 39.24150,
    "start_finish_lon": -77.99240,
    "start_finish_heading_deg": 88.0,
    "geofence_radius_m": 500.0,
    "track_length_m": 3219.0,
    # LineString traces: S/F → T1 → T2 → T3/4 → T5 → T6 →
    # back straight → T7 → T8 → T9 → T10 → S/F
    "geometry_wkt": (
        "LINESTRING("
        "-77.99240 39.24150,"   # Start/finish line
        "-77.98980 39.24140,"   # Turn 1 apex (hard right)
        "-77.98920 39.24050,"   # Turn 2 entry
        "-77.98860 39.23950,"   # Turn 3 apex
        "-77.98950 39.23850,"   # Turn 4 exit
        "-77.99100 39.23820,"   # Turn 5 (left)
        "-77.99280 39.23870,"   # Turn 6 (right, onto back straight)
        "-77.99500 39.23900,"   # Back straight mid
        "-77.99620 39.23950,"   # Turn 7 entry (right)
        "-77.99650 39.24050,"   # Turn 8 apex
        "-77.99550 39.24130,"   # Turn 9
        "-77.99380 39.24150,"   # Turn 10 apex (right, onto S/F straight)
        "-77.99240 39.24150"    # Back to start/finish
        ")"
    ),
    "sectors": [
        # Sector 1 ends at T5 exit / onto back half (~45% of lap)
        {
            "sector_number": 1,
            "trigger_lat": 39.23820,
            "trigger_lon": -77.99100,
            "trigger_heading_deg": 75.0,
        },
        # Sector 2 ends at T8 apex (~78% of lap)
        {
            "sector_number": 2,
            "trigger_lat": 39.24050,
            "trigger_lon": -77.99650,
            "trigger_heading_deg": 355.0,
        },
        # Sector 3 ends at start/finish (implicit)
    ],
}


def upgrade() -> None:
    c = CIRCUIT
    op.execute(f"""
        INSERT INTO circuits (
            id, name, country, timezone,
            start_finish_lat, start_finish_lon,
            start_finish_heading_deg, geofence_radius_m,
            track_length_m, geometry, created_at
        ) VALUES (
            '{c["id"]}',
            $${c["name"]}$$,
            $${c["country"]}$$,
            $${c["timezone"]}$$,
            {c["start_finish_lat"]},
            {c["start_finish_lon"]},
            {c["start_finish_heading_deg"]},
            {c["geofence_radius_m"]},
            {c["track_length_m"]},
            ST_GeomFromText($${c["geometry_wkt"]}$$, 4326),
            now()
        )
        ON CONFLICT (id) DO NOTHING
    """)

    for sector in c["sectors"]:
        heading_sql = (
            str(sector["trigger_heading_deg"])
            if sector.get("trigger_heading_deg") is not None
            else "NULL"
        )
        op.execute(f"""
            INSERT INTO circuit_sectors (
                id, circuit_id, sector_number,
                trigger_lat, trigger_lon, trigger_heading_deg
            ) VALUES (
                uuid_generate_v4(),
                '{c["id"]}',
                {sector["sector_number"]},
                {sector["trigger_lat"]},
                {sector["trigger_lon"]},
                {heading_sql}
            )
            ON CONFLICT (circuit_id, sector_number) DO NOTHING
        """)


def downgrade() -> None:
    op.execute(f"DELETE FROM circuits WHERE id = '{CIRCUIT['id']}'")
