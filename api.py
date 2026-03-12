from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from logic.ingestion import ArchivesIngestion
from npc_brain import NPCBrain
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import shutil
from typing import Any, List, Optional

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

    yield  # Application runs here

    # Cleanup on shutdown (if needed)
    print("Shutting down...")


app = FastAPI(title="Sentient AI API", lifespan=lifespan)

# CORS middleware for frontend integration
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


class ChatInput(BaseModel):
    message: str
    api_key: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    success: bool


class SourceInfo(BaseModel):
    name: str
    path: str
    size: int


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


def get_supabase_client() -> Client:
    global supabase_client

    if supabase_client is not None:
        return supabase_client

    if create_client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase Python client is not installed. Run `uv sync` to install "
                "backend dependencies."
            ),
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase storage is not configured. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY."
            ),
        )

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


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_archives() -> ArchivesIngestion:
    return ArchivesIngestion()


def get_or_create_brain(api_key: Optional[str] = None) -> NPCBrain:
    global brain

    resolved_key = (
        api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    if not resolved_key:
        raise ValueError("API Key not found. Please provide one or set it in .env")

    if brain is None or (api_key and brain.api_key != api_key):
        brain = NPCBrain(api_key=resolved_key)

    return brain


@app.get("/health")
def health_check():
    archives = get_archives()
    return {
        "status": "online",
        "brain_loaded": brain is not None,
        "index_loaded": archives.load_index() is not None,
        "source_count": len(archives.list_sources()),
    }


@app.post("/v1/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatInput):
    try:
        active_brain = get_or_create_brain(payload.api_key)
        reply = active_brain.ask(payload.message)
        return ChatResponse(response=reply, success=True)

    except ValueError:
        return ChatResponse(
            response="Please provide an API key or set it in the environment.",
            success=False,
        )

    except Exception as e:
        print(f"Chat Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a document to be ingested into the knowledge base."""
    global brain

    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Save the uploaded file
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        safe_name = os.path.basename(file.filename)
        if not safe_name.endswith((".pdf", ".txt")):
            raise HTTPException(
                status_code=400, detail="Only PDF and TXT files are supported"
            )

        file_path = os.path.join("data", safe_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        get_archives().ingest(file_path)

        if brain:
            brain.refresh_knowledge()

        return {
            "success": True,
            "message": f"File '{safe_name}' uploaded and indexed.",
            "filename": safe_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/sources")
def list_sources():
    """List all uploaded source documents."""
    sources = get_archives().list_sources()
    return {"sources": sources, "count": len(sources)}


@app.delete("/v1/sources/{filename}")
def delete_source(filename: str):
    """Delete a source document."""
    global brain
    safe_name = os.path.basename(filename)
    file_path = os.path.join("data", safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(file_path)
        get_archives().rebuild_index()

        if brain:
            brain.refresh_knowledge()

        return {"success": True, "message": f"File '{safe_name}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chats")
def list_chats(client_id: str):
    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("chat_sessions")
            .select("*")
            .eq("client_id", client_id)
            .order("updated_at", desc=True)
            .execute()
        )

        sessions = [
            serialize_session_summary(record).model_dump()
            for record in (response.data or [])
        ]
        return {"sessions": sessions, "count": len(sessions)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chats/{chat_id}", response_model=ChatSessionDetail)
def get_chat(chat_id: str, client_id: str):
    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("chat_sessions")
            .select("*")
            .eq("id", chat_id)
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        return serialize_session_detail(response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chats", response_model=ChatSessionDetail)
def create_chat(payload: ChatSessionPayload):
    supabase = get_supabase_client()
    timestamp = current_timestamp()

    try:
        response = (
            supabase.table("chat_sessions")
            .insert(
                {
                    "client_id": payload.client_id,
                    "title": payload.title or "New chat",
                    "preview": payload.preview,
                    "messages": [message.model_dump() for message in payload.messages],
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create chat")

        return serialize_session_detail(response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/chats/{chat_id}", response_model=ChatSessionDetail)
def update_chat(chat_id: str, payload: ChatSessionPayload):
    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("chat_sessions")
            .update(
                {
                    "title": payload.title or "New chat",
                    "preview": payload.preview,
                    "messages": [message.model_dump() for message in payload.messages],
                    "updated_at": current_timestamp(),
                }
            )
            .eq("id", chat_id)
            .eq("client_id", payload.client_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        return serialize_session_detail(response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/chats/{chat_id}")
def delete_chat(chat_id: str, client_id: str):
    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("chat_sessions")
            .delete()
            .eq("id", chat_id)
            .eq("client_id", client_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        return {"success": True, "message": "Chat deleted."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
