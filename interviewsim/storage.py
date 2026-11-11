from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text

from interviewsim.config import settings


def _make_engine():
    if settings.database_url.startswith("sqlite:"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(settings.database_url, connect_args={"check_same_thread": False})
    return create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=300)


engine = _make_engine()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS interview_sessions (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        candidate_name TEXT NOT NULL,
        challenge_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        deadline_at TEXT NOT NULL,
        state TEXT NOT NULL,
        transcript_json TEXT NOT NULL,
        submission_source TEXT,
        scorecard_json TEXT,
        workflow_run_id TEXT,
        updated_at TEXT NOT NULL
    )
    """
    with engine.begin() as connection:
        connection.execute(text(ddl))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_room_user ON interview_sessions(room_id, user_id, state)"))


def _decode(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row._mapping)
    result["transcript"] = json.loads(result.pop("transcript_json") or "[]")
    raw_scorecard = result.pop("scorecard_json")
    result["scorecard"] = json.loads(raw_scorecard) if raw_scorecard else None
    return result


def create_session(room_id: str, user_id: str, candidate_name: str, challenge_id: str, started_at: datetime, deadline_at: datetime) -> dict[str, Any]:
    session_id = str(uuid4())
    values = {
        "id": session_id,
        "room_id": room_id,
        "user_id": user_id,
        "candidate_name": candidate_name,
        "challenge_id": challenge_id,
        "started_at": started_at.isoformat(),
        "deadline_at": deadline_at.isoformat(),
        "state": "active",
        "transcript_json": "[]",
        "submission_source": None,
        "scorecard_json": None,
        "workflow_run_id": None,
        "updated_at": utc_now().isoformat(),
    }
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO interview_sessions
            (id, room_id, user_id, candidate_name, challenge_id, started_at, deadline_at, state,
             transcript_json, submission_source, scorecard_json, workflow_run_id, updated_at)
            VALUES (:id, :room_id, :user_id, :candidate_name, :challenge_id, :started_at, :deadline_at,
                    :state, :transcript_json, :submission_source, :scorecard_json, :workflow_run_id, :updated_at)"""),
            values,
        )
        row = connection.execute(text("SELECT * FROM interview_sessions WHERE id = :id"), {"id": session_id}).first()
    return _decode(row) or {}


def get_session(session_id: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM interview_sessions WHERE id = :id"), {"id": session_id}).first()
    return _decode(row)


def get_active_session(room_id: str, user_id: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT * FROM interview_sessions WHERE room_id = :room AND user_id = :user AND state IN ('active', 'grading') ORDER BY started_at DESC LIMIT 1"),
            {"room": room_id, "user": user_id},
        ).first()
    return _decode(row)


def update_session(session_id: str, **fields: Any) -> dict[str, Any] | None:
    allowed = {
        "state", "transcript_json", "submission_source", "scorecard_json", "workflow_run_id",
        "candidate_name", "deadline_at",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_session(session_id)
    updates["updated_at"] = utc_now().isoformat()
    assignments = ", ".join(f"{key} = :{key}" for key in updates)
    updates["id"] = session_id
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE interview_sessions SET {assignments} WHERE id = :id"), updates)
        row = connection.execute(text("SELECT * FROM interview_sessions WHERE id = :id"), {"id": session_id}).first()
    return _decode(row)


def append_message(session: dict[str, Any], role: str, content: str) -> list[dict[str, str]]:
    transcript = session["transcript"]
    transcript.append({"role": role, "content": content, "at": utc_now().isoformat()})
    update_session(session["id"], transcript_json=json.dumps(transcript, ensure_ascii=False))
    return transcript

