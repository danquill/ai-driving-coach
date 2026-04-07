"""Ideal lap construction — combine best sector from each recorded lap."""

from __future__ import annotations


def construct_ideal_lap(
    lap_sectors: list[dict],
    laps: list[dict],
) -> dict:
    """
    Construct a theoretical best lap by picking the fastest sector time from
    any valid lap (excluding outlaps, inlaps, and invalid laps).

    Args:
        lap_sectors: all lap_sectors rows for the session, each with:
                     lap_id, sector_number, sector_time_ms
        laps: all laps for the session, each with:
              id, lap_number, is_outlap, is_inlap, is_valid

    Returns:
        Dict: {theoretical_time_ms, sector_sources: [{sector_number, lap_id, sector_time_ms}]}
    """
    # Build set of valid lap IDs (exclude outlap, inlap, invalid)
    valid_lap_ids = {
        str(lap["id"])
        for lap in laps
        if not lap.get("is_outlap", False)
        and not lap.get("is_inlap", False)
        and lap.get("is_valid", True)
    }

    if not valid_lap_ids:
        return {"theoretical_time_ms": 0, "sector_sources": []}

    # Filter lap_sectors to valid laps only
    valid_sectors = [
        s for s in lap_sectors
        if str(s["lap_id"]) in valid_lap_ids
    ]

    if not valid_sectors:
        return {"theoretical_time_ms": 0, "sector_sources": []}

    # Group by sector_number — find best (min) for each
    sector_best: dict[int, dict] = {}
    for sector in valid_sectors:
        snum = int(sector["sector_number"])
        sms = sector.get("sector_time_ms")
        if sms is None:
            continue
        sms = int(sms)
        if snum not in sector_best or sms < sector_best[snum]["sector_time_ms"]:
            sector_best[snum] = {
                "sector_number": snum,
                "lap_id": str(sector["lap_id"]),
                "sector_time_ms": sms,
            }

    if not sector_best:
        return {"theoretical_time_ms": 0, "sector_sources": []}

    sector_sources = sorted(sector_best.values(), key=lambda s: s["sector_number"])
    theoretical_time_ms = sum(s["sector_time_ms"] for s in sector_sources)

    return {
        "theoretical_time_ms": theoretical_time_ms,
        "sector_sources": sector_sources,
    }
