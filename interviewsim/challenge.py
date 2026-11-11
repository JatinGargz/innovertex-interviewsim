from __future__ import annotations

CHALLENGE_ID = "python-sliding-window-v1"
CHALLENGE_TITLE = "The Sliding Window Rate Limiter"
CHALLENGE_ROLE = "Backend Engineer"
CHALLENGE_MINUTES = 45

CHALLENGE_BRIEF = """You are reviewing a small Python service that limits requests per user. The intended policy is a rolling window: each user may make at most N accepted requests during the previous W seconds. A request exactly W seconds after an earlier accepted request is outside that window. Rejected requests must not extend the user's lockout.

The current implementation is failing in production around burst traffic and window boundaries. Find the behavioral defects, explain your reasoning, and submit a corrected single Python file.

Interface: `RateLimiter(max_requests, window_seconds)` and `allow(user_id, now) -> bool`. `now` is a numeric timestamp provided by the caller. Different users have independent limits. The candidate should preserve the public interface and should not add external dependencies.

You have 45 minutes. You may ask the interviewer about requirements or production constraints. The interviewer will not reveal the hidden evaluation cases."""

STARTER_CODE = '''from collections import defaultdict, deque


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
'''

PUBLIC_RUBRIC = {
    "root_cause": "Identifies the incorrect boundary and the limit check; explains how the defects affect request behavior.",
    "code_quality": "Preserves the interface, keeps state scoped by user, and uses clear, maintainable logic.",
    "edge_cases": "Reasons about exact expiry, repeated rejected requests, and independent users.",
    "communication": "States a debugging plan, asks useful clarifying questions, and explains the final change clearly.",
}

# Evaluator-only scenarios. Never include these in challenge or session API responses.
HIDDEN_CASES = [
    "one_request_is_allowed",
    "requests_stop_at_the_limit",
    "exact_boundary_expires_old_request",
    "rejected_requests_do_not_extend_lockout",
    "users_have_independent_windows",
    "expired_history_allows_a_new_burst",
]

