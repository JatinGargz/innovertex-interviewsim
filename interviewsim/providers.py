from __future__ import annotations

import json
from typing import Any

import httpx

from interviewsim.config import settings

INTERVIEWER_SYSTEM = """You are a thoughtful senior backend engineer running a timed debugging interview. Keep replies concise and natural. Answer the candidate's direct question. Do not reveal hidden test cases, the answer key, or a complete implementation. Ask what they think before giving an unsolicited hint. When asked to clarify requirements, restate only the confirmed contract. Encourage the candidate to explain their reasoning and tradeoffs. Do not claim you ran code or tests."""



def interviewer_system(challenge: dict) -> str:
    return (
        f"{INTERVIEWER_SYSTEM}\n\n"
        f"Current challenge: {challenge['title']} ({challenge['category']}).\n"
        f"Confirmed challenge contract:\n{challenge['brief']}\n\n"
        f"The public evaluation dimensions are: {json.dumps(challenge['rubric'])}"
    )


def fallback_interviewer_reply(question: str, remaining_seconds: int, challenge: dict) -> str:
    q = question.lower()
    if any(word in q for word in ("requirement", "spec", "contract", "boundary", "limit", "expire", "attempt", "retry", "duplicate", "cache")):
        contract = challenge["brief"].split("\n\n", 1)[0]
        return f"The confirmed contract is: {contract} Which edge behavior would you like to reason through first?"
    if any(word in q for word in ("hint", "where should", "what should", "how do i start")):
        return f"Start by tracing one concrete input through the current implementation and comparing it with the contract. What state or boundary condition would you inspect first? You have about {remaining_seconds // 60} minutes left."
    return f"For this {challenge['category']} round, focus on correctness against the stated contract and explain the edge case you're tracing. Which behavior are you investigating? You have about {remaining_seconds // 60} minutes left."


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

