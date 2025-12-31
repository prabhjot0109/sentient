from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from npc_brain import NPCBrain
from contextlib import asynccontextmanager
import os
import shutil
from typing import Optional

# Global brain instance
brain = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global brain
    try:
        default_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if default_key:
            brain = NPCBrain(api_key=default_key)
            # Pre-load any existing data files
            data_dir = "data"
            if os.path.exists(data_dir):
                for file in os.listdir(data_dir):
                    if file.endswith((".pdf", ".txt")):
                        file_path = os.path.join(data_dir, file)
                        brain.learn_from_file(file_path)
                        print(f"Loaded: {file}")
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


@app.get("/health")
def health_check():
    return {"status": "online", "brain_loaded": brain is not None}


@app.post("/v1/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatInput):
    global brain

    try:
        if not brain:
            if payload.api_key:
                brain = NPCBrain(api_key=payload.api_key)
                # Load any existing data files
                data_dir = "data"
                if os.path.exists(data_dir):
                    for file in os.listdir(data_dir):
                        if file.endswith((".pdf", ".txt")):
                            brain.learn_from_file(os.path.join(data_dir, file))
            else:
                return ChatResponse(
                    response="Please provide an API key or set it in the environment.",
                    success=False,
                )

        reply = brain.ask(payload.message)
        return ChatResponse(response=reply, success=True)

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
        file_path = os.path.join("data", file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Learn from the file if brain is initialized
        if brain:
            brain.learn_from_file(file_path)
            return {
                "success": True,
                "message": f"File '{file.filename}' uploaded and processed.",
                "filename": file.filename,
            }
        else:
            return {
                "success": True,
                "message": f"File '{file.filename}' uploaded. Will be processed when API key is set.",
                "filename": file.filename,
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/sources")
def list_sources():
    """List all uploaded source documents."""
    sources = []
    data_dir = "data"

    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith((".pdf", ".txt")):
                file_path = os.path.join(data_dir, file)
                sources.append(
                    {
                        "name": file,
                        "path": file_path,
                        "size": os.path.getsize(file_path),
                    }
                )

    return {"sources": sources, "count": len(sources)}


@app.delete("/v1/sources/{filename}")
def delete_source(filename: str):
    """Delete a source document."""
    file_path = os.path.join("data", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(file_path)
        return {"success": True, "message": f"File '{filename}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
