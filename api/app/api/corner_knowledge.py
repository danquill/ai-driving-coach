"""Circuit corner knowledge CRUD endpoints.

Router prefix: /circuits
"""

from __future__ import annotations

import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.dependencies import require_admin
from app.schemas.knowledge import (
    CornerKnowledgeCreate,
    CornerKnowledgeResponse,
    CornerKnowledgeUpdate,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/circuits", tags=["corner-knowledge"])


async def _get_circuit_or_404(circuit_id: uuid.UUID, db) -> None:
    row = await db.fetchrow("SELECT id FROM circuits WHERE id = $1", circuit_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")


def _row_to_knowledge(row) -> CornerKnowledgeResponse:
    d = dict(row)
    # asyncpg returns JSONB as a Python list/dict already
    return CornerKnowledgeResponse(**d)


# ---------------------------------------------------------------------------
# GET /circuits/{circuit_id}/corner-knowledge
# ---------------------------------------------------------------------------

@router.get("/{circuit_id}/corner-knowledge", response_model=list[CornerKnowledgeResponse])
async def list_corner_knowledge(
    circuit_id: uuid.UUID,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """List all corner knowledge entries for a circuit."""
    await _get_circuit_or_404(circuit_id, db)
    rows = await db.fetch(
        """
        SELECT id, circuit_id, corner_number, typical_phase_of_interest,
               known_handling_tendency, correct_technique,
               incorrect_recommendations, coaching_notes, source,
               created_at, updated_at
        FROM circuit_corner_knowledge
        WHERE circuit_id = $1
        ORDER BY COALESCE(corner_number, 0), created_at
        """,
        circuit_id,
    )
    return [_row_to_knowledge(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /circuits/{circuit_id}/corner-knowledge
# ---------------------------------------------------------------------------

@router.post(
    "/{circuit_id}/corner-knowledge",
    response_model=CornerKnowledgeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_corner_knowledge(
    circuit_id: uuid.UUID,
    body: CornerKnowledgeCreate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Create a corner knowledge entry."""
    await _get_circuit_or_404(circuit_id, db)
    incorrect_json = (
        json.dumps(body.incorrect_recommendations)
        if body.incorrect_recommendations is not None
        else None
    )
    row = await db.fetchrow(
        """
        INSERT INTO circuit_corner_knowledge
            (circuit_id, corner_number, typical_phase_of_interest,
             known_handling_tendency, correct_technique,
             incorrect_recommendations, coaching_notes, source)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
        RETURNING id, circuit_id, corner_number, typical_phase_of_interest,
                  known_handling_tendency, correct_technique,
                  incorrect_recommendations, coaching_notes, source,
                  created_at, updated_at
        """,
        circuit_id,
        body.corner_number,
        body.typical_phase_of_interest,
        body.known_handling_tendency,
        body.correct_technique,
        incorrect_json,
        body.coaching_notes,
        body.source,
    )
    return _row_to_knowledge(row)


# ---------------------------------------------------------------------------
# PATCH /circuits/{circuit_id}/corner-knowledge/{knowledge_id}
# ---------------------------------------------------------------------------

@router.patch("/{circuit_id}/corner-knowledge/{knowledge_id}", response_model=CornerKnowledgeResponse)
async def update_corner_knowledge(
    circuit_id: uuid.UUID,
    knowledge_id: uuid.UUID,
    body: CornerKnowledgeUpdate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Update a corner knowledge entry. Only fields present in the request body are updated."""
    await _get_circuit_or_404(circuit_id, db)

    # Use exclude_unset so explicitly-passed null clears the field
    updates = body.model_dump(exclude_unset=True)

    # Always set updated_at
    set_clauses = ["updated_at = now()"]
    params: list = []
    idx = 1

    for field, value in updates.items():
        if field == "incorrect_recommendations":
            set_clauses.append(f"{field} = ${idx}::jsonb")
            params.append(json.dumps(value) if value is not None else None)
        else:
            set_clauses.append(f"{field} = ${idx}")
            params.append(value)
        idx += 1

    params.extend([knowledge_id, circuit_id])

    row = await db.fetchrow(
        f"""
        UPDATE circuit_corner_knowledge
        SET {", ".join(set_clauses)}
        WHERE id = ${idx} AND circuit_id = ${idx + 1}
        RETURNING id, circuit_id, corner_number, typical_phase_of_interest,
                  known_handling_tendency, correct_technique,
                  incorrect_recommendations, coaching_notes, source,
                  created_at, updated_at
        """,
        *params,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge entry not found")
    return _row_to_knowledge(row)


# ---------------------------------------------------------------------------
# DELETE /circuits/{circuit_id}/corner-knowledge/{knowledge_id}
# ---------------------------------------------------------------------------

@router.delete("/{circuit_id}/corner-knowledge/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_corner_knowledge(
    circuit_id: uuid.UUID,
    knowledge_id: uuid.UUID,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Delete a corner knowledge entry."""
    await _get_circuit_or_404(circuit_id, db)
    result = await db.execute(
        "DELETE FROM circuit_corner_knowledge WHERE id = $1 AND circuit_id = $2",
        knowledge_id,
        circuit_id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge entry not found")
