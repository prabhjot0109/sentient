"""Request bodies for the API-key routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KeyInput(BaseModel):
    label: str | None = Field(default=None, max_length=200)
