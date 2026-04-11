"""Event CRUD endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.event import (
    AssignSessionsRequest,
    CreateEventRequest,
    EventResponse,
    UpdateEventRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


def _row_to_response(row) -> EventResponse:
    return EventResponse(**dict(row))


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: CreateEventRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        """
        INSERT INTO events (owner_id, circuit_id, name, event_date, notes)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        uuid.UUID(str(current_user["id"])),
        body.circuit_id,
        body.name,
        body.event_date,
        body.notes,
    )
    return await _fetch_event(row["id"], db)


@router.get("/", response_model=list[EventResponse])
async def list_events(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = await db.fetch(
        """
        SELECT e.*, c.name AS circuit_name
        FROM events e
        LEFT JOIN circuits c ON c.id = e.circuit_id
        WHERE e.owner_id = $1
        ORDER BY e.event_date DESC NULLS LAST, e.created_at DESC
        """,
        uuid.UUID(str(current_user["id"])),
    )
    return [_row_to_response(r) for r in rows]


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: UpdateEventRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_owner(event_id, current_user, db)

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await _fetch_event(event_id, db)

    set_clauses = []
    values = []
    for i, (col, val) in enumerate(updates.items(), start=2):
        set_clauses.append(f"{col} = ${i}")
        values.append(val)

    await db.execute(
        f"UPDATE events SET {', '.join(set_clauses)} WHERE id = $1",
        event_id, *values,
    )
    return await _fetch_event(event_id, db)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_owner(event_id, current_user, db)
    # Sessions get event_id = NULL via ON DELETE SET NULL FK
    await db.execute("DELETE FROM events WHERE id = $1", event_id)


@router.patch("/{event_id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def assign_sessions(
    event_id: uuid.UUID,
    body: AssignSessionsRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Replace the set of sessions belonging to this event.

    Sessions in body.session_ids get event_id set to this event.
    Sessions previously in this event but not in the list get event_id = NULL.
    Only sessions owned by the current user can be assigned.
    """
    await _require_owner(event_id, current_user, db)
    owner_id = uuid.UUID(str(current_user["id"]))

    async with db.transaction():
        # Clear existing assignments for this event
        await db.execute(
            "UPDATE sessions SET event_id = NULL WHERE event_id = $1 AND owner_id = $2",
            event_id, owner_id,
        )
        # Assign new set (only sessions owned by this user)
        if body.session_ids:
            await db.execute(
                """
                UPDATE sessions SET event_id = $1
                WHERE id = ANY($2::uuid[]) AND owner_id = $3
                """,
                event_id,
                [str(sid) for sid in body.session_ids],
                owner_id,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_event(event_id: uuid.UUID, db) -> EventResponse:
    row = await db.fetchrow(
        """
        SELECT e.*, c.name AS circuit_name
        FROM events e
        LEFT JOIN circuits c ON c.id = e.circuit_id
        WHERE e.id = $1
        """,
        event_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _row_to_response(row)


async def _require_owner(event_id: uuid.UUID, current_user: dict, db) -> None:
    row = await db.fetchrow("SELECT owner_id FROM events WHERE id = $1", event_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
