from __future__ import annotations

import base64
import json

import httpx

from interviewsim.challenge import HIDDEN_CASES
from interviewsim.config import settings

RESULT_MARKER = "__INTERVIEWSIM_RESULT__"

# This runner is sent as the submitted program. Candidate source arrives only on stdin,
# then runs in Judge0's isolated process with its time/memory/network limits.
HIDDEN_RUNNER = r'''import json
import sys

source = sys.stdin.read()
case_results = []

def execute_case(case_id):
    namespace = {}
    try:
        exec(compile(source, "candidate_submission.py", "exec"), namespace, namespace)
        limiter_type = namespace.get("RateLimiter")
        if not isinstance(limiter_type, type):
            raise AssertionError("RateLimiter class was not found")

        if case_id == "one_request_is_allowed":
            limiter = limiter_type(2, 10)
            assert limiter.allow("alice", 0) is True
        elif case_id == "requests_stop_at_the_limit":
            limiter = limiter_type(2, 10)
            assert limiter.allow("alice", 0) is True
            assert limiter.allow("alice", 1) is True
            assert limiter.allow("alice", 2) is False
        elif case_id == "exact_boundary_expires_old_request":
            limiter = limiter_type(1, 5)
            assert limiter.allow("alice", 100) is True
            assert limiter.allow("alice", 105) is True
        elif case_id == "rejected_requests_do_not_extend_lockout":
            limiter = limiter_type(2, 10)
            assert limiter.allow("alice", 0) is True
            assert limiter.allow("alice", 1) is True
            assert limiter.allow("alice", 2) is False
            assert limiter.allow("alice", 3) is False
            assert limiter.allow("alice", 10) is True
        elif case_id == "users_have_independent_windows":
            limiter = limiter_type(1, 10)
            assert limiter.allow("alice", 0) is True
            assert limiter.allow("alice", 1) is False
            assert limiter.allow("bob", 1) is True
        elif case_id == "expired_history_allows_a_new_burst":
            limiter = limiter_type(3, 10)
            assert limiter.allow("alice", 0) is True
            assert limiter.allow("alice", 1) is True
            assert limiter.allow("alice", 2) is True
            assert limiter.allow("alice", 10) is True
            assert limiter.allow("alice", 11) is True
            assert limiter.allow("alice", 12) is True
        else:
            raise AssertionError("Unknown evaluator case")
        return {"id": case_id, "passed": True}
    except BaseException as exc:
        message = str(exc).replace("\n", " ")[:160]
        return {"id": case_id, "passed": False, "detail": type(exc).__name__ + (": " + message if message else "")}

for name in __CASE_IDS__:
    case_results.append(execute_case(name))

print("__INTERVIEWSIM_RESULT__" + json.dumps({"cases": case_results}, separators=(",", ":")))
'''


def make_runner_source() -> str:
    names = json.dumps(HIDDEN_CASES)
    return HIDDEN_RUNNER.replace("__CASE_IDS__", names)


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.judge0_api_key:
        headers["X-Auth-Token"] = settings.judge0_api_key
        headers["X-RapidAPI-Key"] = settings.judge0_api_key
    if settings.judge0_api_host:
        headers["X-RapidAPI-Host"] = settings.judge0_api_host
    return headers


def _decode_field(value: str | None) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value, validate=True).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        return value


async def grade_source(source_code: str) -> dict:
    if not settings.judge0_base_url:
        raise RuntimeError("JUDGE0_BASE_URL is not configured; candidate code will not be run locally.")
    payload = {
        "source_code": base64.b64encode(make_runner_source().encode()).decode(),
        "stdin": base64.b64encode(source_code.encode()).decode(),
        "language_id": settings.judge0_language_id,
        "cpu_time_limit": 5,
        "memory_limit": 131072,
        "enable_network": False,
    }
    url = f"{settings.judge0_base_url}/submissions?base64_encoded=true&wait=true"
    async with httpx.AsyncClient(timeout=70) as client:
        response = await client.post(url, headers=_headers(), json=payload)
        response.raise_for_status()
        result = response.json()

    status = (result.get("status") or {}).get("description", "Unknown")
    stdout = _decode_field(result.get("stdout"))
    marker_index = stdout.rfind(RESULT_MARKER)
    if status != "Accepted" or marker_index < 0:
        details = _decode_field(result.get("compile_output")) or _decode_field(result.get("stderr")) or result.get("message") or status
        return {
            "status": "sandbox_error",
            "status_description": status,
            "error": str(details)[:800],
            "cases": [{"id": case_id, "passed": False} for case_id in HIDDEN_CASES],
            "passed": 0,
            "total": len(HIDDEN_CASES),
        }

    raw_result = stdout[marker_index + len(RESULT_MARKER):].strip().splitlines()[0]
    parsed = json.loads(raw_result)
    cases = parsed.get("cases", [])
    passed = sum(1 for case in cases if case.get("passed"))
    return {
        "status": "completed",
        "status_description": status,
        "cases": cases,
        "passed": passed,
        "total": len(HIDDEN_CASES),
        "time": result.get("time"),
        "memory": result.get("memory"),
    }

