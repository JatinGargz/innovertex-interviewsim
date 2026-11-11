from __future__ import annotations

import json
from typing import Any

import httpx

from interviewsim.challenge import CHALLENGE_BRIEF, PUBLIC_RUBRIC
from interviewsim.config import settings

INTERVIEWER_SYSTEM = f"""You are a thoughtful senior backend engineer running a timed debugging interview. Keep replies concise and natural. Answer the candidate's direct question. Do not reveal hidden test cases, the answer key, or a complete implementation. Ask what they think before giving an unsolicited hint. When asked to clarify requirements, restate only the confirmed contract. Encourage the candidate to explain their reasoning and tradeoffs. Do not claim you ran code or tests.

Challenge brief:\n{CHALLENGE_BRIEF}

The public evaluation dimensions are: {json.dumps(PUBLIC_RUBRIC)}"""


def fallback_interviewer_reply(question: str, remaining_seconds: int) -> str:
    q = question.lower()
    if any(word in q for word in ("requirement", "spec", "window", "boundary", "limit")):
        return "The stated contract is per user: at most N accepted requests in the rolling W-second window. An accepted request exactly W seconds old is outside the current window, and a rejected request should not extend the limit. Which part would you like to reason through first?"
    if any(word in q for word in ("traffic", "production", "scale", "request per", "rps")):
        return "For this round, focus on correctness for independent users under bursts and exact window boundaries. At larger scale we would also discuss storage and coordination across instances, but keep the submitted implementation dependency-free as the brief requests."
    return f"I can clarify the contract: this is a per-user rolling-window limiter, and the `now` value is supplied by the caller. What behavior do you expect for the case you're investigating? You have about {remaining_seconds // 60} minutes left."


async def chat_completion(messages: list[dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 500) -> str:
    if not settings.openai_api_key or not settings.openai_model:
        raise RuntimeError("The interviewer model is not configured.")
    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(f"{settings.openai_base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
    return body["choices"][0]["message"]["content"].strip()

