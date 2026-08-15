"""Request bodies for the credential-vault routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CredentialInput(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    api_key: str = Field(min_length=1)
