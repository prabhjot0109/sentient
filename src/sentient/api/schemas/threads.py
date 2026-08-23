"""Request bodies for the thread routes."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ThreadRenameInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # min_length alone accepts "   ", which renders as an invisible sidebar row.
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped
