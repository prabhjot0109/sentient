"""Provider client construction for chat models.

This is the adapter half of the old `logic/rag_engine.py`: it knows how to
talk to Google, Groq, HuggingFace and every OpenAI-wire-compatible provider,
and nothing about prompts, retrieval or answering. `NPCBrain` -- the domain
half -- lives in `sentient.services.rag` and sits one layer above.

Splitting them is what removes the last adapters->services import edge in the
codebase: `adapters/documents.py` needs `build_chat_model`, and before the
split reaching it meant importing from a module that also held a service.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()


@lru_cache(maxsize=16)
def build_chat_model(
    provider: str,
    model_name: str,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
) -> BaseChatModel:
    if provider == "google":
        # Gemini Flash "thinks" before replying by default, which adds latency we
        # don't want for short, spoken in-character answers. thinking_budget=0
        # skips that reasoning pass and returns the answer directly.
        # max_retries=2 (default 6) because the langchain client retries 429s
        # with exponential backoff regardless of cause; a daily quota error
        # isn't transient, so retrying it 6 times just makes every request
        # hang for up to a minute before failing anyway.
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            timeout=timeout,
            thinking_budget=0,
            max_retries=2,
        )

    if provider == "groq":
        # The default model (llama-3.3-70b-versatile) doesn't reason, so replies
        # are returned immediately. For reasoning-capable models like
        # openai/gpt-oss-120b, set GROQ_REASONING_EFFORT (e.g. "low") and
        # GROQ_REASONING_FORMAT="hidden" in .env to keep replies fast and free of
        # visible chain-of-thought. We only forward them when set, because Groq
        # 400s if reasoning params are sent to a non-reasoning model.
        # max_retries=2 keeps a rate-limited request from hanging on long
        # exponential backoff: Groq free-tier 429s are usually a spent quota.
        groq_kwargs: dict[str, Any] = {}
        effort = os.getenv("GROQ_REASONING_EFFORT")
        if effort:
            groq_kwargs["reasoning_effort"] = effort
        reasoning_format = os.getenv("GROQ_REASONING_FORMAT")
        if reasoning_format:
            groq_kwargs["reasoning_format"] = reasoning_format
        return ChatGroq(
            model=model_name,
            # LangChain declares SecretStr but its validator coerces a plain str.
            api_key=api_key,  # type: ignore[arg-type]
            timeout=timeout,
            max_retries=2,
            **groq_kwargs,
        )

    if provider == "huggingface":
        # Deferred for the reason documents.py:build_embeddings states: this import
        # drags torch and transformers in, and every other provider pays for it.
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

        return ChatHuggingFace(
            # HuggingFaceEndpoint's stub requires `model` and an int timeout; at
            # runtime a validator fills `model` from `repo_id` and the timeout is
            # passed straight to httpx, which takes a float.
            llm=HuggingFaceEndpoint(  # type: ignore[call-arg]
                repo_id=model_name,
                huggingfacehub_api_token=api_key,
                timeout=timeout,  # type: ignore[arg-type]
            )
        )

    # openai, cerebras, and openrouter all speak the OpenAI wire format; they
    # differ only in base_url (resolved in config) and their API key.
    # max_retries=2 matches the other providers — don't hang on rate limits.
    return ChatOpenAI(
        model=model_name,
        # Same SecretStr-vs-str stub gap as ChatGroq above.
        api_key=api_key,  # type: ignore[arg-type]
        base_url=base_url,
        timeout=timeout,
        max_retries=2,
    )
