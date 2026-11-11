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
    CHALLENGES,
    DEFAULT_CHALLENGE_ID,
    challenge_for_command,
    get_challenge,
    list_challenges,
)
from interviewsim.config import settings
from interviewsim.nonilion import CanonicalNonilionEvent, NonilionReply
from interviewsim.providers import interviewer_system, chat_completion, fallback_interviewer_reply
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
    challenge_id: str = Field(default=DEFAULT_CHALLENGE_ID, max_length=100)


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


def _public_challenge(challenge_id: str = DEFAULT_CHALLENGE_ID) -> dict[str, Any]:
    challenge = get_challenge(challenge_id)
    return {
        "id": challenge["id"],
        "title": challenge["title"],
        "role": challenge["role"],
        "category": challenge["category"],
        "file_name": challenge["file_name"],
        "duration_minutes": settings.session_minutes or challenge["duration_minutes"],
        "brief": challenge["brief"],
        "starter_code": challenge["starter_code"],
        "rubric": challenge["rubric"],
    }


async def _answer_candidate(session: dict[str, Any], content: str) -> tuple[str, dict[str, Any]]:
    transcript = append_message(session, "user", content)
    remaining = _seconds_remaining(session)
    recent = transcript[-16:]
    challenge = get_challenge(session["challenge_id"])
    messages = [{"role": "system", "content": interviewer_system(challenge)}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in recent)
    try:
        reply = await chat_completion(messages)
    except Exception:
        reply = fallback_interviewer_reply(content, remaining, challenge)
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
                "challenge_id": session["challenge_id"],
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


@app.get("/api/challenges")
async def challenges() -> list[dict[str, Any]]:
    return list_challenges()


@app.get("/api/challenge")
async def challenge(challenge_id: str = DEFAULT_CHALLENGE_ID) -> dict[str, Any]:
    if challenge_id not in CHALLENGES:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    return _public_challenge(challenge_id)


@app.post("/api/sessions")
async def start_session(body: StartSessionRequest) -> dict[str, Any]:
    if body.challenge_id not in CHALLENGES:
        raise HTTPException(status_code=422, detail="Choose one of the available debugging rounds.")
    selected = get_challenge(body.challenge_id)
    now = datetime.now(timezone.utc)
    duration = settings.session_minutes or selected["duration_minutes"]
    session = create_session(
        room_id=body.room_id.strip() or "browser-demo",
        user_id=body.user_id.strip() or "local-candidate",
        candidate_name=body.candidate_name.strip() or "Candidate",
        challenge_id=selected["id"],
        started_at=now,
        deadline_at=now + timedelta(minutes=duration),
    )
    return {"challenge": _public_challenge(selected["id"]), "session": _public_session(session)}


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
    normalized_message = message.lower().strip()
    is_start = normalized_message == "start" or normalized_message == "/start" or normalized_message == "start interview" or normalized_message.startswith("start ") or normalized_message.startswith("/start ")
    if is_start:
        if active:
            return NonilionReply(event_id=body.event_id, text=f"You already have an active round. Session {active['id'][:8]} has {max(0, _seconds_remaining(active) // 60)} minutes left.", session_id=active["id"], state=active["state"])
        requested = "" if normalized_message in {"start interview", "/start interview"} else normalized_message.removeprefix("/start").removeprefix("start").strip()
        selected = challenge_for_command(requested) if requested else get_challenge(DEFAULT_CHALLENGE_ID)
        if selected is None:
            choices = ", ".join(item["command"] for item in list_challenges())
            return NonilionReply(event_id=body.event_id, text=f"Unknown round. Choose one: {choices}.")
        now = datetime.now(timezone.utc)
        duration = settings.session_minutes or selected["duration_minutes"]
        active = create_session(body.room_id, body.user_id, body.user_name, selected["id"], now, now + timedelta(minutes=duration))
        text = f"{selected['title']} · {selected['category']}\n\n{selected['brief']}\n\nStarter code:\n```python\n{selected['starter_code']}```\n\nYour {duration}-minute timer starts now. Ask a question or send a file_submission event with your complete source code."
        append_message(active, "assistant", text)
        return NonilionReply(event_id=body.event_id, text=text, session_id=active["id"], state="active")

    if not active:
        choices = ", ".join(item["command"] for item in list_challenges())
        return NonilionReply(event_id=body.event_id, text=f"Send `start` or `start <round>` to begin. Available rounds: {choices}.")

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

