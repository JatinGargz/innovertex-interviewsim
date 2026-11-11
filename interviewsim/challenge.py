from __future__ import annotations

DEFAULT_CHALLENGE_ID = "python-sliding-window-v1"
CHALLENGE_MINUTES = 45

PUBLIC_RUBRIC = {
    "root_cause": "Identifies the behavioral defects and explains their impact.",
    "code_quality": "Preserves the public interface and uses clear, maintainable logic.",
    "edge_cases": "Reasons about boundaries, repeated calls, and independent inputs.",
    "communication": "States a debugging plan, asks useful clarifying questions, and explains the fix.",
}


CHALLENGES = {
    "python-sliding-window-v1": {
        "id": "python-sliding-window-v1",
        "command": "rate-limiter",
        "file_name": "rate_limiter.py",
        "title": "The Sliding Window Rate Limiter",
        "role": "Backend Engineer",
        "category": "Rate limiting",
        "duration_minutes": CHALLENGE_MINUTES,
        "brief": """You are reviewing a small Python service that limits requests per user. The intended policy is a rolling window: each user may make at most N accepted requests during the previous W seconds. A request exactly W seconds after an earlier accepted request is outside that window. Rejected requests must not extend the user's lockout.

The current implementation is failing in production around burst traffic and window boundaries. Find the behavioral defects, explain your reasoning, and submit a corrected single Python file.

Interface: `RateLimiter(max_requests, window_seconds)` and `allow(user_id, now) -> bool`. `now` is a numeric timestamp provided by the caller. Different users have independent limits. Preserve the public interface and do not add external dependencies.

You have 45 minutes. Ask the interviewer about requirements or production constraints. The interviewer will not reveal the hidden evaluation cases.""",
        "starter_code": '''from collections import defaultdict, deque


class RateLimiter:
    """Allow up to max_requests per user in a rolling time window."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    def allow(self, user_id: str, now: float) -> bool:
        timestamps = self.requests[user_id]

        # Drop requests that are outside this user's active window.
        while timestamps and now - timestamps[0] > self.window_seconds:
            timestamps.popleft()

        if len(timestamps) > self.max_requests:
            return False

        timestamps.append(now)
        return True
''',
        "rubric": PUBLIC_RUBRIC,
        "hidden_cases": [
            "one_request_is_allowed",
            "requests_stop_at_the_limit",
            "exact_boundary_expires_old_request",
            "rejected_requests_do_not_extend_lockout",
            "users_have_independent_windows",
            "expired_history_allows_a_new_burst",
        ],
    },
    "python-ttl-cache-v1": {
        "id": "python-ttl-cache-v1",
        "command": "cache",
        "file_name": "ttl_cache.py",
        "title": "The Expiring Cache",
        "role": "Backend Engineer",
        "category": "Caching · TTL · LRU",
        "duration_minutes": CHALLENGE_MINUTES,
        "brief": """A Python API cache returns stale values under load and occasionally evicts a frequently used key. The intended cache has a fixed capacity, expires an entry when `now >= expires_at`, and evicts the least recently used live entry when full. A successful `get` and an update to an existing key both make that key most recently used. Expired entries must not occupy capacity.

Find the behavioral defects and submit one corrected Python file.

Interface: `TTLCache(max_size)`, `set(key, value, now, ttl_seconds)`, and `get(key, now)`. `get` returns the value or `None` when absent or expired. Assume positive capacity and non-negative TTLs; use only the Python standard library. The interviewer will not reveal hidden evaluation cases.""",
        "starter_code": '''class TTLCache:
    """A bounded cache with expiration and least-recently-used eviction."""

    def __init__(self, max_size: int):
        self.max_size = max_size
        self.entries = {}

    def set(self, key, value, now: float, ttl_seconds: float) -> None:
        self._remove_expired(now)
        self.entries[key] = (value, now + ttl_seconds)
        if len(self.entries) > self.max_size:
            oldest = next(iter(self.entries))
            del self.entries[oldest]

    def get(self, key, now: float):
        if key not in self.entries:
            return None
        value, expires_at = self.entries[key]
        if now > expires_at:
            del self.entries[key]
            return None
        return value

    def _remove_expired(self, now: float) -> None:
        for key, (_, expires_at) in list(self.entries.items()):
            if now > expires_at:
                del self.entries[key]
''',
        "rubric": PUBLIC_RUBRIC,
        "hidden_cases": [
            "cache_value_available_before_expiry",
            "cache_expires_at_exact_boundary",
            "get_refreshes_lru_recency",
            "overwrite_refreshes_lru_recency",
            "expired_entries_do_not_consume_capacity",
            "expired_lookup_is_a_miss",
        ],
    },
    "python-retry-policy-v1": {
        "id": "python-retry-policy-v1",
        "command": "retry",
        "file_name": "retry_policy.py",
        "title": "The Retry Queue That Won't Stop",
        "role": "Backend Engineer",
        "category": "Retries · Backoff",
        "duration_minutes": CHALLENGE_MINUTES,
        "brief": """A background worker is retrying failed jobs too many times and creating a retry storm. The policy counts the initial request as attempt 1. `next_delay(failed_attempt)` receives a one-based attempt number and returns the delay before the next retry, or `None` when the retry budget is exhausted. Delays use exponential backoff: `base_delay_seconds * 2 ** (failed_attempt - 1)`, capped at `max_delay_seconds`.

Find the off-by-one and boundary defects. Submit one corrected Python file.

Interface: `RetryPolicy(max_attempts, base_delay_seconds, max_delay_seconds)` and `next_delay(failed_attempt) -> float | None`. `max_attempts` includes the initial request. The interviewer will not reveal hidden evaluation cases.""",
        "starter_code": '''class RetryPolicy:
    """Calculate a capped exponential retry delay."""

    def __init__(self, max_attempts: int, base_delay_seconds: float, max_delay_seconds: float):
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds

    def next_delay(self, failed_attempt: int):
        # The caller passes a one-based attempt number.
        if failed_attempt > self.max_attempts:
            return None
        delay = self.base_delay_seconds * (2 ** failed_attempt)
        return min(delay, self.max_delay_seconds)
''',
        "rubric": PUBLIC_RUBRIC,
        "hidden_cases": [
            "first_retry_uses_base_delay",
            "retry_delay_doubles_each_attempt",
            "retry_delay_is_capped",
            "final_attempt_has_no_retry",
            "attempt_after_budget_has_no_retry",
            "single_attempt_policy_never_retries",
        ],
    },
    "python-payment-idempotency-v1": {
        "id": "python-payment-idempotency-v1",
        "command": "payments",
        "file_name": "payment_ledger.py",
        "title": "The Duplicate Payment Incident",
        "role": "Backend Engineer",
        "category": "Payments · Idempotency",
        "duration_minutes": CHALLENGE_MINUTES,
        "brief": """A payment endpoint sometimes charges a customer twice when a client retries after a timeout. The ledger must treat `payment_id` as an idempotency key: a valid payment ID can increase the total at most once. `charge` returns `True` only when it records a new positive payment, and returns `False` for duplicate IDs or non-positive amounts. A duplicate must never change the total, even if its amount differs.

Find the correctness defects and submit one corrected Python file. Do not add external dependencies.

Interface: `PaymentLedger()` with `charge(payment_id, amount) -> bool` and a numeric `total_charged` attribute. The interviewer will not reveal hidden evaluation cases.""",
        "starter_code": '''class PaymentLedger:
    """Track successful charges while supporting safe client retries."""

    def __init__(self):
        self.processed_payment_ids = set()
        self.total_charged = 0

    def charge(self, payment_id: str, amount: float) -> bool:
        # Record the amount before checking whether this request was already handled.
        self.total_charged += amount
        if payment_id in self.processed_payment_ids:
            return False
        self.processed_payment_ids.add(payment_id)
        return True
''',
        "rubric": PUBLIC_RUBRIC,
        "hidden_cases": [
            "new_payment_is_recorded",
            "duplicate_payment_does_not_charge_twice",
            "duplicate_with_different_amount_is_ignored",
            "distinct_payment_ids_are_both_recorded",
            "non_positive_amount_is_rejected",
        ],
    },
}


# Backward-compatible aliases for the original rate-limiter round.
CHALLENGE_ID = DEFAULT_CHALLENGE_ID
CHALLENGE_TITLE = CHALLENGES[DEFAULT_CHALLENGE_ID]["title"]
CHALLENGE_ROLE = CHALLENGES[DEFAULT_CHALLENGE_ID]["role"]
CHALLENGE_BRIEF = CHALLENGES[DEFAULT_CHALLENGE_ID]["brief"]
STARTER_CODE = CHALLENGES[DEFAULT_CHALLENGE_ID]["starter_code"]
HIDDEN_CASES = CHALLENGES[DEFAULT_CHALLENGE_ID]["hidden_cases"]


def get_challenge(challenge_id: str = DEFAULT_CHALLENGE_ID) -> dict:
    return CHALLENGES.get(challenge_id, CHALLENGES[DEFAULT_CHALLENGE_ID])


def list_challenges() -> list[dict]:
    return [
        {
            "id": challenge["id"],
            "title": challenge["title"],
            "role": challenge["role"],
            "category": challenge["category"],
            "duration_minutes": challenge["duration_minutes"],
            "command": challenge["command"],
            "file_name": challenge["file_name"],
        }
        for challenge in CHALLENGES.values()
    ]


def hidden_cases_for(challenge_id: str) -> list[str]:
    return get_challenge(challenge_id)["hidden_cases"]


def challenge_for_command(command: str) -> dict | None:
    normalized = command.strip().lower().replace("_", "-")
    for challenge in CHALLENGES.values():
        if normalized in {challenge["command"], challenge["id"], challenge["title"].lower()}:
            return challenge
    return None
