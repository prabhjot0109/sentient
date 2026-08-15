"""Request bodies for the API-key routes."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class KeyInput(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
