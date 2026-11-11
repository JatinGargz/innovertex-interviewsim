from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CanonicalNonilionEvent(BaseModel):
    """Internal event shape; map the verified Nonilion Bot API payload into this model."""

    event_id: str = Field(min_length=1, max_length=200)
    room_id: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    user_name: str = Field(default="Candidate", max_length=120)
    text: str = Field(default="", max_length=4000)
    event_type: Literal["message", "file_submission"] = "message"
    source_code: str | None = Field(default=None, max_length=50000)


class NonilionReply(BaseModel):
    event_id: str
    text: str
    session_id: str | None = None
    state: str | None = None

