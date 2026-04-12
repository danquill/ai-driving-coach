"""Session CRUD + file upload endpoints."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import PurePosixPath

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.database import get_db
from app.dependencies import get_current_user, DEMO_SESSION_ID
from app.schemas.file import RawFileResponse, UploadResponse
from app.schemas.session import CreateSessionRequest, SessionResponse, UpdateSessionRequest
from app.services.storage import RAW_FILES_BUCKET, get_storage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

_ALLOWED_EXTENSIONS = {".vbo", ".csv", ".apexsession", ".drk", ".xdrk", ".ld"}
_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_response(row) -> SessionResponse:
    d = dict(row)
    return SessionResponse(**d)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        """
        INSERT INTO sessions (owner_id, vehicle_id, circuit_id, name, session_date, ambient_temp_c, notes, session_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        uuid.UUID(str(current_user["id"])),
        body.vehicle_id,
        body.circuit_id,
        body.name,
        body.session_date,
        body.ambient_temp_c,
        body.notes,
        body.session_type,
    )
    logger.info("session_created", session_id=str(row["id"]), owner_id=str(current_user["id"]))
    return _row_to_response(row)


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 50,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = await db.fetch(
        """
        SELECT s.*,
               c.name AS circuit_name,
               (SELECT MIN(l.lap_time_ms)
                FROM laps l
                WHERE l.session_id = s.id
                  AND l.is_valid = true
                  AND l.is_outlap = false
                  AND l.is_inlap = false
                  AND l.lap_time_ms IS NOT NULL
               ) AS best_lap_time_ms
        FROM sessions s
        LEFT JOIN circuits c ON c.id = s.circuit_id
        WHERE s.owner_id = $1 AND s.status != 'deleted'
        ORDER BY s.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        uuid.UUID(str(current_user["id"])),
        limit,
        skip,
    )
    return [_row_to_response(r) for r in rows]


@router.get("/demo", response_model=SessionResponse)
async def get_demo_session(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the shared demo session (read-only, accessible to all authenticated users)."""
    row = await db.fetchrow(
        """
        SELECT s.*,
               c.name AS circuit_name,
               (SELECT MIN(l.lap_time_ms)
                FROM laps l
                WHERE l.session_id = s.id
                  AND l.is_valid = true
                  AND l.is_outlap = false
                  AND l.is_inlap = false
                  AND l.lap_time_ms IS NOT NULL
               ) AS best_lap_time_ms
        FROM sessions s
        LEFT JOIN circuits c ON c.id = s.circuit_id
        WHERE s.id = $1 AND s.status != 'deleted'
        """,
        uuid.UUID(DEMO_SESSION_ID),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo session not found")
    return _row_to_response(row)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT * FROM sessions WHERE id = $1 AND status != 'deleted'",
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if str(row["owner_id"]) != str(current_user["id"]) and str(session_id) != DEMO_SESSION_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _row_to_response(row)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT * FROM sessions WHERE id = $1 AND status != 'deleted'",
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_response(row)

    set_clauses = []
    values = []
    for i, (col, val) in enumerate(updates.items(), start=2):
        set_clauses.append(f"{col} = ${i}")
        values.append(val)

    query = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
    updated = await db.fetchrow(query, session_id, *values)
    return _row_to_response(updated)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "SELECT * FROM sessions WHERE id = $1 AND status != 'deleted'",
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.execute(
        "UPDATE sessions SET status = 'deleted' WHERE id = $1",
        session_id,
    )


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@router.post("/{session_id}/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    session_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Verify session ownership
    session_row = await db.fetchrow(
        "SELECT * FROM sessions WHERE id = $1 AND status != 'deleted'",
        session_id,
    )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if str(session_row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Validate extension
    original_filename = file.filename or "unknown"
    suffix = PurePosixPath(original_filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{suffix}'. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    # Enforce size limit via Content-Length header if available
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 500 MB limit",
        )

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 500 MB limit",
        )

    # Compute SHA-256
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Determine format from extension
    format_map = {
        ".vbo": "vbo",
        ".csv": "csv",
        ".apexsession": "apexsession",
        ".drk": "drk",
        ".xdrk": "xdrk",
        ".ld": "ld",
    }
    file_format = format_map[suffix]

    # Generate IDs
    raw_file_id = uuid.uuid4()

    # Storage key: {session_id}/{raw_file_id}/{original_filename}
    storage_key = f"{session_id}/{raw_file_id}/{original_filename}"

    # Upload to MinIO
    storage = get_storage()
    content_type_map = {
        ".vbo": "application/octet-stream",
        ".csv": "text/csv",
        ".drk": "application/octet-stream",
        ".xdrk": "application/octet-stream",
        ".ld": "application/octet-stream",
    }
    storage.upload_file(
        bucket=RAW_FILES_BUCKET,
        key=storage_key,
        data=file_bytes,
        content_type=content_type_map.get(suffix, "application/octet-stream"),
    )

    # Insert raw_files record
    await db.execute(
        """
        INSERT INTO raw_files (id, session_id, original_filename, storage_key, file_format, file_size_bytes, sha256)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        raw_file_id,
        session_id,
        original_filename,
        storage_key,
        file_format,
        len(file_bytes),
        sha256,
    )

    # Insert analysis_jobs record
    job_id = uuid.uuid4()
    await db.execute(
        """
        INSERT INTO analysis_jobs (id, session_id, requested_by, job_type, status, input_params)
        VALUES ($1, $2, $3, 'parse', 'queued', $4)
        """,
        job_id,
        session_id,
        uuid.UUID(str(current_user["id"])),
        f'{{"raw_file_id": "{raw_file_id}", "storage_key": "{storage_key}"}}',
    )

    # Dispatch Celery parse task via lightweight client
    from app.celery_client import celery_app
    celery_app.send_task(
        "worker.app.tasks.parse.parse_telemetry_file",
        args=[str(session_id), str(raw_file_id), str(job_id), storage_key],
        task_id=str(job_id),
        queue="parse",
    )

    logger.info(
        "file_uploaded",
        session_id=str(session_id),
        raw_file_id=str(raw_file_id),
        job_id=str(job_id),
        filename=original_filename,
        size=len(file_bytes),
    )

    return UploadResponse(
        raw_file_id=raw_file_id,
        session_id=session_id,
        job_id=job_id,
        message=f"File '{original_filename}' uploaded successfully. Parse job queued.",
    )


# ---------------------------------------------------------------------------
# List files for session
# ---------------------------------------------------------------------------

@router.get("/{session_id}/files", response_model=list[RawFileResponse])
async def list_session_files(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    session_row = await db.fetchrow(
        "SELECT * FROM sessions WHERE id = $1 AND status != 'deleted'",
        session_id,
    )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if str(session_row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    rows = await db.fetch(
        "SELECT * FROM raw_files WHERE session_id = $1 ORDER BY uploaded_at DESC",
        session_id,
    )
    return [RawFileResponse(**dict(r)) for r in rows]
