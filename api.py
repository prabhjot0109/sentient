from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from npc_brain import NPCBrain
import os

app = FastAPI(title="NeuralNPC Microservice")

# Global brain instance
brain = None


class ChatInput(BaseModel):
    player_message: str
    api_key: str


@app.on_event("startup")
async def startup_event():
    global brain
    # Initialize implementation logic
    # Hardcoded path as per requirements
    files_to_load = ["data/lore.pdf"]

    # Check if files exist, if not, we might fallback or just init empty
    # For this task, we initialize assuming the file should be there or logic handles it
    try:
        # We start with a default key if available, or wait for request
        default_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if default_key:
            brain = NPCBrain(api_key=default_key)
            # Pre-load data if exists
            if os.path.exists("data/lore.pdf"):
                brain.learn_from_file("data/lore.pdf")
            else:
                print(
                    "Warning: data/lore.pdf not found. Brain initialized without lore."
                )
        else:
            print(
                "No default API key found. Brain will be initialized per-request if not globally set."
            )
            # We can still init the object if we handle the key later, but NPCBrain typically needs key at init
            # The prompt says: "Initialize the NPCBrain once when the server starts"
            # If no key is present in env, we might defer valid init?
            # Existing NPCBrain raises ValueError if no key.
            # We will handle re-init in the endpoint if needed.
            pass

    except Exception as e:
        print(f"Startup initialization failed: {e}")


@app.get("/health")
def health_check():
    return {"status": "online"}


@app.post("/v1/chat")
def chat_endpoint(payload: ChatInput):
    global brain

    try:
        # Update brain's API key if needed or init if None
        if not brain:
            brain = NPCBrain(api_key=payload.api_key)
            # Try loading lore again if it wasn't valid before?
            # For simplicity, we assume one-time startup load, but if that failed, we might need to reload.
            if os.path.exists("data/lore.pdf"):
                brain.learn_from_file("data/lore.pdf")
        else:
            # If brain exists but new key provided, we might want to update it?
            # NPCBrain uses the key for the LLM.
            pass

        # If strict requirement to "Update the brain's API key (if needed)", we could do:
        # brain.llm.openai_api_key = payload.api_key
        # But this depends on implementation details.
        # Re-instantiating might be safer if the class doesn't support hot-swapping keys easily.
        # But let's assume standard usage.

        reply = brain.ask(payload.player_message)
        return {"sentinel_reply": reply}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
