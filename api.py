from __future__ import annotations

import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from time import perf_counter
from typing import Any, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from logic.chat_store import LocalChatStore
from logic.config import load_rag_settings
from logic.ingestion import ArchivesIngestion
from npc_brain import NPCBrain

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore[misc,assignment]
    create_client = None

# Global brain instance
brain: Optional[NPCBrain] = None
supabase_client: Optional[Client] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global brain
    try:
        default_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if default_key:
            brain = NPCBrain(api_key=default_key)
        else:
            print("No default API key found. Brain will be initialized per-request.")
    except Exception as e:
        print(f"Startup initialization failed: {e}")

    yield

    print("Shutting down...")


app = FastAPI(title="Sentient AI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RetrievedChunk(BaseModel):
    content: str
    score: Optional[float] = None
    source: str
    page_label: str = ""
    chunk_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatInput(BaseModel):
    message: str
    api_key: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class ChatResponse(BaseModel):
    response: str
    success: bool
    sources: list[RetrievedChunk] = Field(default_factory=list)
    top_k: Optional[int] = None
    retrieval_ms: Optional[float] = None


class RetrievalInput(BaseModel):
    query: str
    api_key: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


class RetrievalResponse(BaseModel):
    success: bool
    query: str
    top_k: int
    retrieval_ms: float
    chunks: list[RetrievedChunk] = Field(default_factory=list)


class StoredMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str


class ChatSessionPayload(BaseModel):
    client_id: str
    title: str
    preview: str = ""
    messages: List[StoredMessage] = Field(default_factory=list)


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    preview: str
    created_at: str
    updated_at: str
    message_count: int


class ChatSessionDetail(ChatSessionSummary):
    messages: List[StoredMessage]


@lru_cache(maxsize=1)
def get_default_archives() -> ArchivesIngestion:
    return ArchivesIngestion()


@lru_cache(maxsize=1)
def get_local_chat_store() -> LocalChatStore:
    settings = load_rag_settings()
    return LocalChatStore(os.path.join(settings.data_dir, "chat_sessions.json"))


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_archives(api_key: Optional[str] = None) -> ArchivesIngestion:
    if api_key:
        return ArchivesIngestion(api_key=api_key)
    return get_default_archives()


def has_supabase_chat_store() -> bool:
    return bool(
        create_client is not None
        and os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )


def get_supabase_client() -> Client:
    global supabase_client

    if supabase_client is not None:
        return supabase_client

    if create_client is None:
        raise RuntimeError(
            "Supabase Python client is not installed. Run `uv sync` to install it."
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError("Supabase storage is not configured.")

    supabase_client = create_client(supabase_url, supabase_key)
    return supabase_client


def serialize_session_summary(record: dict) -> ChatSessionSummary:
    messages = record.get("messages") or []
    return ChatSessionSummary(
        id=record["id"],
        title=record.get("title") or "New chat",
        preview=record.get("preview") or "",
        created_at=record.get("created_at") or "",
        updated_at=record.get("updated_at") or record.get("created_at") or "",
        message_count=len(messages),
    )


def serialize_session_detail(record: dict) -> ChatSessionDetail:
    summary = serialize_session_summary(record)
    messages = record.get("messages") or []
    return ChatSessionDetail(**summary.model_dump(), messages=messages)


def list_chat_records(client_id: str) -> list[dict]:
    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .select("*")
            .eq("client_id", client_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return response.data or []

    return get_local_chat_store().list(client_id)


def get_chat_record(chat_id: str, client_id: str) -> dict | None:
    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .select("*")
            .eq("id", chat_id)
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    return get_local_chat_store().get(chat_id, client_id)


def create_chat_record(payload: ChatSessionPayload) -> dict:
    message_payload = [message.model_dump() for message in payload.messages]

    if has_supabase_chat_store():
        timestamp = current_timestamp()
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .insert(
                {
                    "client_id": payload.client_id,
                    "title": payload.title or "New chat",
                    "preview": payload.preview,
                    "messages": message_payload,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create chat")
        return response.data[0]

    return get_local_chat_store().create(
        client_id=payload.client_id,
        title=payload.title,
        preview=payload.preview,
        messages=message_payload,
    )


def update_chat_record(chat_id: str, payload: ChatSessionPayload) -> dict | None:
    message_payload = [message.model_dump() for message in payload.messages]

    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .update(
                {
                    "title": payload.title or "New chat",
                    "preview": payload.preview,
                    "messages": message_payload,
                    "updated_at": current_timestamp(),
                }
            )
            .eq("id", chat_id)
            .eq("client_id", payload.client_id)
            .execute()
        )
        return response.data[0] if response.data else None

    return get_local_chat_store().update(
        chat_id,
        client_id=payload.client_id,
        title=payload.title,
        preview=payload.preview,
        messages=message_payload,
    )


def delete_chat_record(chat_id: str, client_id: str) -> dict | None:
    if has_supabase_chat_store():
        response = (
            get_supabase_client()
            .table("chat_sessions")
            .delete()
            .eq("id", chat_id)
            .eq("client_id", client_id)
            .execute()
        )
        return response.data[0] if response.data else None

    return get_local_chat_store().delete(chat_id, client_id)


def get_or_create_brain(api_key: Optional[str] = None) -> NPCBrain:
    global brain

    resolved_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not resolved_key:
        raise ValueError("API Key not found. Please provide one or set it in .env")

    if brain is None or brain.api_key != resolved_key:
        brain = NPCBrain(api_key=resolved_key)

    return brain


@app.get("/health")
def health_check():
    archives = get_default_archives()
    settings = load_rag_settings()
    index_metadata = archives.get_index_metadata()

    return {
        "status": "online",
        "brain_loaded": brain is not None,
        "index_loaded": archives.index_exists(),
        "source_count": len(archives.list_sources()),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "search_type": settings.search_type,
        "top_k": settings.top_k,
        "chat_storage": "supabase" if has_supabase_chat_store() else "local",
        "index_metadata": index_metadata,
    }


@app.post("/v1/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatInput):
    try:
        started_at = perf_counter()
        active_brain = get_or_create_brain(payload.api_key)
        result = active_brain.ask_with_context(payload.message, top_k=payload.top_k)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        return ChatResponse(
            response=result["answer"],
            success=True,
            sources=[RetrievedChunk(**source) for source in result["sources"]],
            top_k=result["top_k"],
            retrieval_ms=elapsed_ms,
        )
    except ValueError:
        return ChatResponse(
            response="Please provide an API key or set it in the environment.",
            success=False,
        )
    except Exception as e:
        print(f"Chat Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/retrieve", response_model=RetrievalResponse)
def retrieve_endpoint(payload: RetrievalInput):
    try:
        started_at = perf_counter()
        archives = get_archives(payload.api_key)
        chunks = archives.retrieve(payload.query, k=payload.top_k)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        serialized_chunks = [
            RetrievedChunk(
                content=document.page_content,
                score=score,
                source=document.metadata.get("source", "unknown"),
                page_label=document.metadata.get("page_label", ""),
                chunk_id=document.metadata.get("chunk_id"),
                metadata=document.metadata,
            )
            for document, score in chunks
        ]
        return RetrievalResponse(
            success=True,
            query=payload.query,
            top_k=payload.top_k or load_rag_settings(payload.api_key).top_k,
            retrieval_ms=elapsed_ms,
            chunks=serialized_chunks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(default=None),
):
    """Upload a document to be ingested into the knowledge base."""
    global brain

    try:
        archives = get_archives(api_key)
        archives.data_dir.mkdir(parents=True, exist_ok=True)

        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        safe_name = os.path.basename(file.filename)
        if not safe_name.lower().endswith((".pdf", ".txt")):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and TXT files are supported",
            )

        file_path = str(archives.data_dir / safe_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        archives.ingest(file_path)

        if brain:
            brain.refresh_knowledge()

        return {
            "success": True,
            "message": f"File '{safe_name}' uploaded and indexed.",
            "filename": safe_name,
            "index_metadata": archives.get_index_metadata(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/sources")
def list_sources():
    """List all uploaded source documents."""
    sources = get_default_archives().list_sources()
    return {"sources": sources, "count": len(sources)}


@app.delete("/v1/sources/{filename}")
def delete_source(filename: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Delete a source document."""
    global brain
    archives = get_archives(x_api_key)
    safe_name = os.path.basename(filename)
    file_path = str(archives.data_dir / safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(file_path)
        archives.rebuild_index()

        if brain:
            brain.refresh_knowledge()

        return {
            "success": True,
            "message": f"File '{safe_name}' deleted.",
            "index_metadata": archives.get_index_metadata(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chats")
def list_chats(client_id: str):
    try:
        sessions = [
            serialize_session_summary(record).model_dump()
            for record in list_chat_records(client_id)
        ]
        return {"sessions": sessions, "count": len(sessions)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chats/{chat_id}", response_model=ChatSessionDetail)
def get_chat(chat_id: str, client_id: str):
    try:
        record = get_chat_record(chat_id, client_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return serialize_session_detail(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chats", response_model=ChatSessionDetail)
def create_chat(payload: ChatSessionPayload):
    try:
        record = create_chat_record(payload)
        return serialize_session_detail(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/chats/{chat_id}", response_model=ChatSessionDetail)
def update_chat(chat_id: str, payload: ChatSessionPayload):
    try:
        record = update_chat_record(chat_id, payload)
        if record is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return serialize_session_detail(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/chats/{chat_id}")
def delete_chat(chat_id: str, client_id: str):
    try:
        record = delete_chat_record(chat_id, client_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"success": True, "message": "Chat deleted."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
