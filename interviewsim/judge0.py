from __future__ import annotations

import base64
import json

import httpx

from interviewsim.challenge import DEFAULT_CHALLENGE_ID, hidden_cases_for
from interviewsim.config import settings

RESULT_MARKER = "__INTERVIEWSIM_RESULT__"

# Candidate code arrives on stdin and runs inside Judge0 with network disabled.
HIDDEN_RUNNER = r'''import json
import sys

source = sys.stdin.read()
challenge_id = __CHALLENGE_ID__
case_results = []

def execute_case(case_id):
    namespace = {}
    try:
        exec(compile(source, "candidate_submission.py", "exec"), namespace, namespace)

        if challenge_id == "python-sliding-window-v1":
            limiter_type = namespace.get("RateLimiter")
            if not isinstance(limiter_type, type):
                raise AssertionError("RateLimiter class was not found")
            if case_id == "one_request_is_allowed":
                assert limiter_type(2, 10).allow("alice", 0) is True
            elif case_id == "requests_stop_at_the_limit":
                limiter = limiter_type(2, 10)
                assert limiter.allow("alice", 0) is True and limiter.allow("alice", 1) is True
                assert limiter.allow("alice", 2) is False
            elif case_id == "exact_boundary_expires_old_request":
                limiter = limiter_type(1, 5)
                assert limiter.allow("alice", 100) is True and limiter.allow("alice", 105) is True
            elif case_id == "rejected_requests_do_not_extend_lockout":
                limiter = limiter_type(2, 10)
                assert limiter.allow("alice", 0) is True and limiter.allow("alice", 1) is True
                assert limiter.allow("alice", 2) is False and limiter.allow("alice", 3) is False
                assert limiter.allow("alice", 10) is True
            elif case_id == "users_have_independent_windows":
                limiter = limiter_type(1, 10)
                assert limiter.allow("alice", 0) is True and limiter.allow("alice", 1) is False
                assert limiter.allow("bob", 1) is True
            elif case_id == "expired_history_allows_a_new_burst":
                limiter = limiter_type(3, 10)
                for now in (0, 1, 2, 10, 11, 12):
                    assert limiter.allow("alice", now) is True
            else:
                raise AssertionError("Unknown evaluator case")

        elif challenge_id == "python-ttl-cache-v1":
            cache_type = namespace.get("TTLCache")
            if not isinstance(cache_type, type):
                raise AssertionError("TTLCache class was not found")
            if case_id == "cache_value_available_before_expiry":
                cache = cache_type(2)
                cache.set("a", 1, 0, 5)
                assert cache.get("a", 4) == 1
            elif case_id == "cache_expires_at_exact_boundary":
                cache = cache_type(2)
                cache.set("a", 1, 0, 5)
                assert cache.get("a", 5) is None
            elif case_id == "get_refreshes_lru_recency":
                cache = cache_type(2)
                cache.set("a", 1, 0, 20)
                cache.set("b", 2, 0, 20)
                assert cache.get("a", 1) == 1
                cache.set("c", 3, 2, 20)
                assert cache.get("b", 2) is None and cache.get("a", 2) == 1
            elif case_id == "overwrite_refreshes_lru_recency":
                cache = cache_type(2)
                cache.set("a", 1, 0, 20)
                cache.set("b", 2, 0, 20)
                cache.set("a", 9, 1, 20)
                cache.set("c", 3, 2, 20)
                assert cache.get("b", 2) is None and cache.get("a", 2) == 9
            elif case_id == "expired_entries_do_not_consume_capacity":
                cache = cache_type(1)
                cache.set("old", 1, 0, 1)
                cache.set("new", 2, 1, 5)
                assert cache.get("new", 1) == 2 and cache.get("old", 1) is None
            elif case_id == "expired_lookup_is_a_miss":
                cache = cache_type(2)
                cache.set("a", 1, 0, 1)
                assert cache.get("a", 3) is None
            else:
                raise AssertionError("Unknown evaluator case")

        elif challenge_id == "python-retry-policy-v1":
            policy_type = namespace.get("RetryPolicy")
            if not isinstance(policy_type, type):
                raise AssertionError("RetryPolicy class was not found")
            if case_id == "first_retry_uses_base_delay":
                assert policy_type(5, 2, 30).next_delay(1) == 2
            elif case_id == "retry_delay_doubles_each_attempt":
                policy = policy_type(5, 2, 30)
                assert policy.next_delay(1) == 2 and policy.next_delay(2) == 4
            elif case_id == "retry_delay_is_capped":
                assert policy_type(8, 3, 8).next_delay(4) == 8
            elif case_id == "final_attempt_has_no_retry":
                assert policy_type(3, 2, 30).next_delay(3) is None
            elif case_id == "attempt_after_budget_has_no_retry":
                assert policy_type(3, 2, 30).next_delay(4) is None
            elif case_id == "single_attempt_policy_never_retries":
                assert policy_type(1, 2, 30).next_delay(1) is None
            else:
                raise AssertionError("Unknown evaluator case")

        elif challenge_id == "python-payment-idempotency-v1":
            ledger_type = namespace.get("PaymentLedger")
            if not isinstance(ledger_type, type):
                raise AssertionError("PaymentLedger class was not found")
            if case_id == "new_payment_is_recorded":
                ledger = ledger_type()
                assert ledger.charge("p-1", 25) is True and ledger.total_charged == 25
            elif case_id == "duplicate_payment_does_not_charge_twice":
                ledger = ledger_type()
                assert ledger.charge("p-1", 25) is True
                assert ledger.charge("p-1", 25) is False and ledger.total_charged == 25
            elif case_id == "duplicate_with_different_amount_is_ignored":
                ledger = ledger_type()
                ledger.charge("p-1", 25)
                assert ledger.charge("p-1", 90) is False and ledger.total_charged == 25
            elif case_id == "distinct_payment_ids_are_both_recorded":
                ledger = ledger_type()
                assert ledger.charge("p-1", 25) is True and ledger.charge("p-2", 10) is True
                assert ledger.total_charged == 35
            elif case_id == "non_positive_amount_is_rejected":
                ledger = ledger_type()
                assert ledger.charge("p-1", 0) is False
                assert ledger.charge("p-2", -5) is False and ledger.total_charged == 0
            else:
                raise AssertionError("Unknown evaluator case")
        else:
            raise AssertionError("Unknown challenge")
        return {"id": case_id, "passed": True}
    except BaseException as exc:
        message = str(exc).replace("\n", " ")[:160]
        return {"id": case_id, "passed": False, "detail": type(exc).__name__ + (": " + message if message else "")}

for name in __CASE_IDS__:
    case_results.append(execute_case(name))

print("__INTERVIEWSIM_RESULT__" + json.dumps({"cases": case_results}, separators=(",", ":")))
'''


def make_runner_source(challenge_id: str = DEFAULT_CHALLENGE_ID) -> str:
    names = json.dumps(hidden_cases_for(challenge_id))
    selected = json.dumps(challenge_id)
    return HIDDEN_RUNNER.replace("__CHALLENGE_ID__", selected).replace("__CASE_IDS__", names)


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


async def grade_source(source_code: str, challenge_id: str = DEFAULT_CHALLENGE_ID) -> dict:
    if not settings.judge0_base_url:
        raise RuntimeError("JUDGE0_BASE_URL is not configured; candidate code will not be run locally.")
    if challenge_id not in {DEFAULT_CHALLENGE_ID, "python-ttl-cache-v1", "python-retry-policy-v1", "python-payment-idempotency-v1"}:
        raise ValueError("Unknown challenge selected for grading.")
    cases = hidden_cases_for(challenge_id)
    payload = {
        "source_code": base64.b64encode(make_runner_source(challenge_id).encode()).decode(),
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
            "cases": [{"id": case_id, "passed": False} for case_id in cases],
            "passed": 0,
            "total": len(cases),
        }

    raw_result = stdout[marker_index + len(RESULT_MARKER):].strip().splitlines()[0]
    parsed = json.loads(raw_result)
    graded_cases = parsed.get("cases", [])
    passed = sum(1 for case in graded_cases if case.get("passed"))
    return {
        "status": "completed",
        "status_description": status,
        "cases": graded_cases,
        "passed": passed,
        "total": len(cases),
        "time": result.get("time"),
        "memory": result.get("memory"),
    }
