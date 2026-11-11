from __future__ import annotations

import hmac
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from render import RenderAsync

from interviewsim.challenge import (
    CHALLENGE_BRIEF,
    CHALLENGE_ID,
    CHALLENGE_MINUTES,
    CHALLENGE_ROLE,
    CHALLENGE_TITLE,
    STARTER_CODE,
)
from interviewsim.config import settings
from interviewsim.nonilion import CanonicalNonilionEvent, NonilionReply
from interviewsim.providers import INTERVIEWER_SYSTEM, chat_completion, fallback_interviewer_reply
from interviewsim.reports import create_scorecard_pdf
from interviewsim.storage import append_message, create_session, get_active_session, get_session, init_db, update_session

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="InterviewSim", version="0.1.0", lifespan=lifespan)


class StartSessionRequest(BaseModel):
    candidate_name: str = Field(default="Candidate", max_length=120)
    room_id: str = Field(default="browser-demo", max_length=200)
    user_id: str = Field(default="local-candidate", max_length=200)


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SubmissionRequest(BaseModel):
    source_code: str = Field(min_length=1, max_length=50000)


class ScorecardCallback(BaseModel):
    session_id: str
    scorecard: dict[str, Any]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _seconds_remaining(session: dict[str, Any]) -> int:
    deadline = _parse_time(session["deadline_at"])
    return max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))


def _public_session(session: dict[str, Any]) -> dict[str, Any]:
    remaining = _seconds_remaining(session) if session["state"] == "active" else 0
    if session["state"] == "active" and remaining == 0:
        update_session(session["id"], state="expired")
        session["state"] = "expired"
    return {
        "id": session["id"],
        "candidate_name": session["candidate_name"],
        "challenge_id": session["challenge_id"],
        "started_at": session["started_at"],
        "deadline_at": session["deadline_at"],
        "remaining_seconds": remaining,
        "state": session["state"],
        "transcript": session["transcript"],
        "scorecard": session["scorecard"],
        "workflow_run_id": session["workflow_run_id"],
    }


def _public_challenge() -> dict[str, Any]:
    return {
        "id": CHALLENGE_ID,
        "title": CHALLENGE_TITLE,
        "role": CHALLENGE_ROLE,
        "duration_minutes": settings.session_minutes or CHALLENGE_MINUTES,
        "brief": CHALLENGE_BRIEF,
        "starter_code": STARTER_CODE,
        "rubric": {
            "root_cause": "Find and explain the behavioral defects.",
            "code_quality": "Keep the interface clear and maintainable.",
            "edge_cases": "Reason about time boundaries, rejected calls, and independent users.",
            "communication": "Explain the debugging plan and tradeoffs.",
        },
    }


async def _answer_candidate(session: dict[str, Any], content: str) -> tuple[str, dict[str, Any]]:
    transcript = append_message(session, "user", content)
    remaining = _seconds_remaining(session)
    recent = transcript[-16:]
    messages = [{"role": "system", "content": INTERVIEWER_SYSTEM}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in recent)
    try:
        reply = await chat_completion(messages)
    except Exception:
        reply = fallback_interviewer_reply(content, remaining)
    append_message(session, "assistant", reply)
    return reply, get_session(session["id"]) or session


async def _start_workflow(session: dict[str, Any], source_code: str) -> str:
    if not settings.render_api_key:
        raise HTTPException(status_code=503, detail="Render grading is not configured yet. Set RENDER_API_KEY and deploy the InterviewSim Workflow.")
    if not settings.app_public_url or not settings.callback_secret:
        raise HTTPException(status_code=503, detail="The Render callback is not configured. Set APP_PUBLIC_URL and INTERNAL_CALLBACK_SECRET.")
    if not settings.judge0_base_url:
        raise HTTPException(status_code=503, detail="The isolated grader is not configured. Set JUDGE0_BASE_URL before accepting submissions.")

    update_session(session["id"], state="grading", submission_source=source_code)
    try:
        client = RenderAsync(token=settings.render_api_key)
        task_run = await client.workflows.start_task(
            f"{settings.render_workflow_slug}/grade_submission",
            {
                "session_id": session["id"],
                "source_code": source_code,
                "transcript": session["transcript"],
            },
        )
    except Exception as exc:
        update_session(session["id"], state="active")
        raise HTTPException(status_code=502, detail=f"Could not start the Render grading workflow ({type(exc).__name__}).") from exc
    update_session(session["id"], workflow_run_id=getattr(task_run, "id", None))
    return str(getattr(task_run, "id", "started"))


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "interviewsim"}


@app.get("/api/challenge")
async def challenge() -> dict[str, Any]:
    return _public_challenge()


@app.post("/api/sessions")
async def start_session(body: StartSessionRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    duration = settings.session_minutes or CHALLENGE_MINUTES
    session = create_session(
        room_id=body.room_id.strip() or "browser-demo",
        user_id=body.user_id.strip() or "local-candidate",
        candidate_name=body.candidate_name.strip() or "Candidate",
        challenge_id=CHALLENGE_ID,
        started_at=now,
        deadline_at=now + timedelta(minutes=duration),
    )
    return {"challenge": _public_challenge(), "session": _public_session(session)}


@app.get("/api/sessions/{session_id}")
async def read_session(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _public_session(session)


@app.get("/api/sessions/{session_id}/scorecard.pdf")
async def download_scorecard(session_id: str) -> Response:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["state"] != "completed" or not session["scorecard"]:
        raise HTTPException(status_code=409, detail="The scorecard is not ready yet.")
    filename = re.sub(r"[^a-z0-9]+", "-", session["candidate_name"].lower()).strip("-")[:40] or "candidate"
    pdf = create_scorecard_pdf(session["scorecard"], session["candidate_name"])
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="interviewsim-scorecard-{filename}.pdf"'},
    )


@app.post("/api/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["state"] != "active" or _seconds_remaining(session) <= 0:
        if session["state"] == "active":
            update_session(session_id, state="expired")
        raise HTTPException(status_code=409, detail="This interview has ended. Submit your code before starting another round.")
    reply, updated = await _answer_candidate(session, body.content.strip())
    return {"reply": reply, "session": _public_session(updated)}


@app.post("/api/sessions/{session_id}/submit")
async def submit(session_id: str, body: SubmissionRequest) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["state"] != "active" or _seconds_remaining(session) <= 0:
        if session["state"] == "active":
            update_session(session_id, state="expired")
        raise HTTPException(status_code=409, detail="This interview has ended. The session can no longer accept a submission.")
    source = body.source_code.strip()
    if not source:
        raise HTTPException(status_code=422, detail="Submit the complete Python file.")
    workflow_run_id = await _start_workflow(session, source)
    return {"state": "grading", "workflow_run_id": workflow_run_id, "message": "Submission received. Render is grading it now; this page will update when the scorecard is ready."}


@app.post("/api/internal/scorecard")
async def receive_scorecard(body: ScorecardCallback, request: Request) -> dict[str, bool]:
    supplied = request.headers.get("X-InterviewSim-Workflow-Secret", "")
    if not settings.callback_secret or not hmac.compare_digest(supplied, settings.callback_secret):
        raise HTTPException(status_code=401, detail="Invalid workflow callback credentials.")
    session = get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    update_session(body.session_id, state="completed", scorecard_json=json.dumps(body.scorecard, ensure_ascii=False))
    return {"stored": True}


@app.post("/api/nonilion/webhook", response_model=NonilionReply)
async def nonilion_webhook(
    body: CanonicalNonilionEvent,
    authorization: str | None = Header(default=None),
) -> NonilionReply:
    if not settings.nonilion_webhook_secret:
        raise HTTPException(status_code=503, detail="Nonilion webhook authentication is not configured.")
    expected = f"Bearer {settings.nonilion_webhook_secret}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook credentials.")

    message = body.text.strip()
    active = get_active_session(body.room_id, body.user_id)
    if active and active["state"] == "active" and _seconds_remaining(active) <= 0:
        update_session(active["id"], state="expired")
        active = None
    if message.lower() in {"start", "/start", "start interview"}:
        if active:
            return NonilionReply(event_id=body.event_id, text=f"You already have an active round. Session {active['id'][:8]} has {max(0, _seconds_remaining(active) // 60)} minutes left.", session_id=active["id"], state=active["state"])
        now = datetime.now(timezone.utc)
        duration = settings.session_minutes or CHALLENGE_MINUTES
        active = create_session(body.room_id, body.user_id, body.user_name, CHALLENGE_ID, now, now + timedelta(minutes=duration))
        text = f"{CHALLENGE_TITLE}\n\n{CHALLENGE_BRIEF}\n\nStarter code:\n```python\n{STARTER_CODE}```\n\nYour {duration}-minute timer starts now. Ask a question or send a file_submission event with your complete source code."
        append_message(active, "assistant", text)
        return NonilionReply(event_id=body.event_id, text=text, session_id=active["id"], state="active")

    if not active:
        return NonilionReply(event_id=body.event_id, text="Send `start` to begin a timed debugging interview.")

    if body.event_type == "file_submission" or message.lower() in {"submit", "/submit"}:
        source = body.source_code
        if not source:
            return NonilionReply(event_id=body.event_id, text="Please attach the complete Python source file in the submission event.", session_id=active["id"], state=active["state"])
        if _seconds_remaining(active) <= 0:
            update_session(active["id"], state="expired")
            return NonilionReply(event_id=body.event_id, text="The round timer has ended, so I could not accept this submission.", session_id=active["id"], state="expired")
        workflow_run_id = await _start_workflow(active, source)
        return NonilionReply(event_id=body.event_id, text=f"Submission received. Render is grading it now (run {workflow_run_id}).", session_id=active["id"], state="grading")

    if message.lower() in {"status", "/status"}:
        return NonilionReply(event_id=body.event_id, text=f"Round status: {active['state']}. Time remaining: {_seconds_remaining(active) // 60} minutes.", session_id=active["id"], state=active["state"])

    if active["state"] != "active" or _seconds_remaining(active) <= 0:
        return NonilionReply(event_id=body.event_id, text="This round has ended. Start a new interview to continue.", session_id=active["id"], state=active["state"])
    reply, _ = await _answer_candidate(active, message)
    return NonilionReply(event_id=body.event_id, text=reply, session_id=active["id"], state="active")

