from __future__ import annotations

import asyncio

import httpx
from render import Retry, TaskContext, Workflows

from interviewsim.config import settings
from interviewsim.grading import assemble_scorecard
from interviewsim.judge0 import grade_source

app = Workflows()


@app.task(name="sandbox_candidate", retry=Retry(max_retries=2, wait_duration_ms=1000), timeout_seconds=120)
async def sandbox_candidate(ctx: TaskContext, source_code: str) -> dict:
    """Run the submitted source through Judge0. This Render task never executes it itself."""
    return await grade_source(source_code)


@app.task(name="review_interview", timeout_seconds=90)
async def review_interview_task(ctx: TaskContext, source_code: str, transcript: list[dict]) -> dict:
    from interviewsim.grading import review_interview

    return await review_interview(source_code, transcript)


async def _post_scorecard(session_id: str, scorecard: dict) -> None:
    if not settings.app_public_url or not settings.callback_secret:
        raise RuntimeError("Set APP_PUBLIC_URL and INTERNAL_CALLBACK_SECRET for the workflow callback.")
    base_url = settings.app_public_url
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            f"{base_url}/api/internal/scorecard",
            headers={"X-InterviewSim-Workflow-Secret": settings.callback_secret},
            json={"session_id": session_id, "scorecard": scorecard},
        )
        response.raise_for_status()


@app.task(name="grade_submission", timeout_seconds=240)
async def grade_submission(ctx: TaskContext, session_id: str, source_code: str, transcript: list[dict]) -> dict:
    """Parallelize sandbox execution and transcript/code review, then deliver one report."""
    technical, interview_review = await asyncio.gather(
        ctx.run(sandbox_candidate, source_code),
        ctx.run(review_interview_task, source_code, transcript),
        return_exceptions=True,
    )
    if isinstance(technical, Exception):
        technical = {
            "status": "service_error",
            "status_description": "Sandbox unavailable",
            "error": f"Judge0 request failed ({type(technical).__name__}).",
            "cases": [],
            "passed": 0,
            "total": 0,
        }
    if isinstance(interview_review, Exception):
        interview_review = {"available": False, "note": f"Interview review failed ({type(interview_review).__name__})."}
    scorecard = assemble_scorecard(session_id, technical, interview_review, transcript)
    await _post_scorecard(session_id, scorecard)
    return scorecard


if __name__ == "__main__":
    app.start()

