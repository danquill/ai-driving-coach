"""Seed circuit data — Laguna Seca, Brands Hatch (Indy), Silverstone (GP),
Spa-Francorchamps, Nurburgring GP.

Coordinates are real-world accurate for start/finish lines.
Sector trigger points are evenly spaced approximations that can be refined
once GPS data is available for each circuit.

Revision ID: 002
Revises: 001
Create Date: 2026-04-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "002"
down_revision: str = "001"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Circuit data
#
# Each circuit entry contains:
#   - Accurate start/finish GPS coordinates
#   - Accurate start/finish heading (degrees true north, clockwise)
#   - Track length (official published figure, in metres)
#   - Geofence radius in metres (generous catch-all around the paddock)
#   - Timezone (IANA)
#   - 2–3 sector trigger points (approximate, evenly spaced around the lap)
#   - A WKT LineString geometry tracing the approximate circuit outline
#     (simplified — major corners captured, not every apex)
#
# Sector triggers are ordered by sector_number (1-indexed).
# The trigger point for sector N marks where that sector ENDS (and N+1 begins).
# ---------------------------------------------------------------------------

CIRCUITS = [
    # =========================================================================
    # Laguna Seca — Weathertech Raceway, Salinas CA, USA
    # Official length: 3.602 km (2.238 mi)
    # Start/finish: Turn 11 exit, heading approximately NW toward T1
    # =========================================================================
    {
        "id": "a1000000-0000-0000-0000-000000000001",
        "name": "Laguna Seca",
        "country": "USA",
        "timezone": "America/Los_Angeles",
        "start_finish_lat": 36.58448,
        "start_finish_lon": -121.75367,
        "start_finish_heading_deg": 305.0,
        "geofence_radius_m": 600.0,
        "track_length_m": 3602.0,
        # LineString traces the 11-turn layout from S/F through the Corkscrew
        # and back. Points captured: S/F → T2 → T3 entry → Corkscrew top →
        # Corkscrew bottom → T9 entry → T11 exit (S/F)
        "geometry_wkt": (
            "LINESTRING("
            "-121.75367 36.58448,"   # Start/finish line
            "-121.75490 36.58680,"   # Turn 2 apex
            "-121.75630 36.58800,"   # Turn 3 entry
            "-121.75900 36.58950,"   # Turn 4 (Corkscrew top)
            "-121.75950 36.58820,"   # Corkscrew bottom (Turn 8b)
            "-121.75750 36.58620,"   # Turn 9 entry (fast right)
            "-121.75500 36.58480,"   # Turn 10 / 11 complex
            "-121.75367 36.58448"    # Back to start/finish
            ")"
        ),
        "sectors": [
            # Sector 1 ends at Turn 4 / Corkscrew top (~36% of lap)
            {
                "sector_number": 1,
                "trigger_lat": 36.58950,
                "trigger_lon": -121.75900,
                "trigger_heading_deg": 220.0,
            },
            # Sector 2 ends at Turn 9 hairpin exit (~70% of lap)
            {
                "sector_number": 2,
                "trigger_lat": 36.58560,
                "trigger_lon": -121.75640,
                "trigger_heading_deg": 130.0,
            },
            # Sector 3 ends at start/finish (lap complete — implicit)
        ],
    },
    # =========================================================================
    # Brands Hatch — Indy Circuit, West Kingsdown, Kent, UK
    # Official length (Indy): 1.929 km (1.198 mi)
    # Start/finish: Main straight, heading approximately NW
    # =========================================================================
    {
        "id": "a2000000-0000-0000-0000-000000000002",
        "name": "Brands Hatch (Indy)",
        "country": "UK",
        "timezone": "Europe/London",
        "start_finish_lat": 51.36096,
        "start_finish_lon": 0.26254,
        "start_finish_heading_deg": 295.0,
        "geofence_radius_m": 400.0,
        "track_length_m": 1929.0,
        # Indy loop: S/F → Paddock Hill Bend → Druids → Graham Hill Bend →
        # Cooper Straight → Surtees → Clearways → Clark Curve → S/F
        "geometry_wkt": (
            "LINESTRING("
            "0.26254 51.36096,"    # Start/finish
            "0.26050 51.35900,"    # Paddock Hill Bend apex
            "0.26120 51.35760,"    # Druids hairpin apex
            "0.26350 51.35800,"    # Graham Hill Bend
            "0.26620 51.35870,"    # Cooper Straight / Surtees entry
            "0.26700 51.36000,"    # Surtees apex
            "0.26580 51.36100,"    # Clearways
            "0.26430 51.36120,"    # Clark Curve
            "0.26254 51.36096"     # Back to start/finish
            ")"
        ),
        "sectors": [
            # Sector 1 ends at Druids hairpin (~40% of lap)
            {
                "sector_number": 1,
                "trigger_lat": 51.35760,
                "trigger_lon": 0.26120,
                "trigger_heading_deg": 60.0,
            },
            # Sector 2 ends at Surtees (~75% of lap)
            {
                "sector_number": 2,
                "trigger_lat": 51.36000,
                "trigger_lon": 0.26700,
                "trigger_heading_deg": 340.0,
            },
        ],
    },
    # =========================================================================
    # Silverstone — Grand Prix Circuit, Northamptonshire, UK
    # Official length (GP): 5.891 km (3.660 mi)
    # Start/finish: Main straight (between Vale & Club)
    # =========================================================================
    {
        "id": "a3000000-0000-0000-0000-000000000003",
        "name": "Silverstone (GP)",
        "country": "UK",
        "timezone": "Europe/London",
        "start_finish_lat": 52.07105,
        "start_finish_lon": -1.01694,
        "start_finish_heading_deg": 165.0,
        "geofence_radius_m": 1200.0,
        "track_length_m": 5891.0,
        # GP layout key points: S/F → Copse → Maggots/Becketts → Chapel →
        # Hangar Straight → Stowe → Vale → Club → S/F
        "geometry_wkt": (
            "LINESTRING("
            "-1.01694 52.07105,"   # Start/finish
            "-1.02100 52.07350,"   # Copse apex
            "-1.02600 52.07300,"   # Maggotts entry
            "-1.02750 52.07100,"   # Becketts apex
            "-1.02550 52.06900,"   # Chapel exit
            "-1.02000 52.06700,"   # Hangar Straight mid
            "-1.01400 52.06550,"   # Stowe entry
            "-1.01100 52.06600,"   # Stowe apex
            "-1.01050 52.06800,"   # Vale
            "-1.01200 52.07000,"   # Club entry
            "-1.01500 52.07100,"   # Club apex
            "-1.01694 52.07105"    # Back to start/finish
            ")"
        ),
        "sectors": [
            # Sector 1 ends at Chapel exit (post-Becketts, ~35% of lap)
            {
                "sector_number": 1,
                "trigger_lat": 52.06900,
                "trigger_lon": -1.02550,
                "trigger_heading_deg": 135.0,
            },
            # Sector 2 ends at Stowe apex (~65% of lap)
            {
                "sector_number": 2,
                "trigger_lat": 52.06600,
                "trigger_lon": -1.01100,
                "trigger_heading_deg": 0.0,
            },
            # Sector 3 ends at start/finish (implicit)
        ],
    },
    # =========================================================================
    # Circuit de Spa-Francorchamps, Belgium
    # Official length: 7.004 km (4.352 mi)
    # Start/finish: Main straight between La Source and Raidillon
    # =========================================================================
    {
        "id": "a4000000-0000-0000-0000-000000000004",
        "name": "Spa-Francorchamps",
        "country": "Belgium",
        "timezone": "Europe/Brussels",
        "start_finish_lat": 50.43714,
        "start_finish_lon": 5.96680,
        "start_finish_heading_deg": 105.0,
        "geofence_radius_m": 1500.0,
        "track_length_m": 7004.0,
        # Key points: S/F → La Source → Eau Rouge/Raidillon → Kemmel Straight →
        # Les Combes → Malmedy → Rivage hairpin → Pouhon → Campus →
        # Stavelot → Blanchimont → Bus Stop → S/F
        "geometry_wkt": (
            "LINESTRING("
            "5.96680 50.43714,"    # Start/finish
            "5.96250 50.43580,"    # La Source hairpin apex
            "5.96400 50.43370,"    # Eau Rouge entry
            "5.97000 50.43250,"    # Raidillon crest
            "5.97500 50.43150,"    # Kemmel Straight mid
            "5.97700 50.43050,"    # Les Combes (chicane) entry
            "5.97500 50.42900,"    # Les Combes exit
            "5.97200 50.42700,"    # Malmedy
            "5.96950 50.42550,"    # Rivage hairpin apex
            "5.96700 50.42600,"    # Rivage exit
            "5.96200 50.42800,"    # Pouhon left-left
            "5.95900 50.43050,"    # Campus
            "5.96200 50.43300,"    # Stavelot
            "5.96600 50.43500,"    # Blanchimont
            "5.96750 50.43600,"    # Bus Stop chicane
            "5.96680 50.43714"     # Back to start/finish
            ")"
        ),
        "sectors": [
            # Sector 1 ends at Les Combes / top of the hill (~35% of lap)
            {
                "sector_number": 1,
                "trigger_lat": 50.43050,
                "trigger_lon": 5.97700,
                "trigger_heading_deg": 215.0,
            },
            # Sector 2 ends at Pouhon entry (~65% of lap)
            {
                "sector_number": 2,
                "trigger_lat": 50.42800,
                "trigger_lon": 5.96200,
                "trigger_heading_deg": 350.0,
            },
            # Sector 3 ends at start/finish (implicit)
        ],
    },
    # =========================================================================
    # Nurburgring GP-Strecke, Nürburg, Germany
    # Official length (GP): 5.148 km (3.199 mi)
    # Start/finish: Main straight (Mercedes arena side)
    # Note: this is the GP circuit, NOT the Nordschleife
    # =========================================================================
    {
        "id": "a5000000-0000-0000-0000-000000000005",
        "name": "Nurburgring GP",
        "country": "Germany",
        "timezone": "Europe/Berlin",
        "start_finish_lat": 50.33462,
        "start_finish_lon": 6.94753,
        "start_finish_heading_deg": 280.0,
        "geofence_radius_m": 1000.0,
        "track_length_m": 5148.0,
        # GP layout key points: S/F → Turn 1 (Mercedes arena) → Turn 6 →
        # Dunlop hairpin → Bit Kurve → Veedol chicane →
        # Ford Kurve → Schumacher S → S/F
        "geometry_wkt": (
            "LINESTRING("
            "6.94753 50.33462,"    # Start/finish
            "6.94400 50.33300,"    # Turn 1 apex (Mercedes arena entry)
            "6.94150 50.33200,"    # Turn 2 / 3
            "6.94000 50.33050,"    # Turn 4
            "6.93900 50.32900,"    # Turn 5 / 6
            "6.93700 50.32750,"    # Turn 7 (Dunlop hairpin approach)
            "6.93500 50.32700,"    # Dunlop hairpin apex
            "6.93600 50.32850,"    # Bit Kurve exit
            "6.94000 50.33000,"    # Veedol chicane
            "6.94300 50.33100,"    # Ford Kurve entry
            "6.94600 50.33250,"    # Ford Kurve exit
            "6.94750 50.33380,"    # Schumacher S
            "6.94753 50.33462"     # Back to start/finish
            ")"
        ),
        "sectors": [
            # Sector 1 ends at Dunlop hairpin (~40% of lap)
            {
                "sector_number": 1,
                "trigger_lat": 50.32700,
                "trigger_lon": 6.93500,
                "trigger_heading_deg": 90.0,
            },
            # Sector 2 ends at Ford Kurve exit (~75% of lap)
            {
                "sector_number": 2,
                "trigger_lat": 50.33250,
                "trigger_lon": 6.94600,
                "trigger_heading_deg": 350.0,
            },
            # Sector 3 ends at start/finish (implicit)
        ],
    },
]


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    for circuit in CIRCUITS:
        # Insert circuit row
        op.execute(f"""
            INSERT INTO circuits (
                id,
                name,
                country,
                timezone,
                start_finish_lat,
                start_finish_lon,
                start_finish_heading_deg,
                geofence_radius_m,
                track_length_m,
                geometry,
                created_at
            ) VALUES (
                '{circuit["id"]}',
                $${circuit["name"]}$$,
                $${circuit["country"]}$$,
                $${circuit["timezone"]}$$,
                {circuit["start_finish_lat"]},
                {circuit["start_finish_lon"]},
                {circuit["start_finish_heading_deg"]},
                {circuit["geofence_radius_m"]},
                {circuit["track_length_m"]},
                ST_GeomFromText($${circuit["geometry_wkt"]}$$, 4326),
                now()
            )
            ON CONFLICT (id) DO NOTHING
        """)

        # Insert sectors for this circuit
        for sector in circuit["sectors"]:
            heading_sql = (
                f"{sector['trigger_heading_deg']}"
                if sector.get("trigger_heading_deg") is not None
                else "NULL"
            )
            op.execute(f"""
                INSERT INTO circuit_sectors (
                    id,
                    circuit_id,
                    sector_number,
                    trigger_lat,
                    trigger_lon,
                    trigger_heading_deg
                ) VALUES (
                    uuid_generate_v4(),
                    '{circuit["id"]}',
                    {sector["sector_number"]},
                    {sector["trigger_lat"]},
                    {sector["trigger_lon"]},
                    {heading_sql}
                )
                ON CONFLICT (circuit_id, sector_number) DO NOTHING
            """)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    circuit_ids = [c["id"] for c in CIRCUITS]
    ids_sql = ", ".join(f"'{cid}'" for cid in circuit_ids)

    # Sectors cascade-delete via FK
    op.execute(f"DELETE FROM circuits WHERE id IN ({ids_sql})")
