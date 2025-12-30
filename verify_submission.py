import sys
import os

print("--- Verifying Deliverables ---")

try:
    import fastapi
    import uvicorn

    print("[OK] FastAPI and Uvicorn are installed.")
except ImportError as e:
    print(f"[FAIL] Missing dependency: {e}")
    sys.exit(1)

try:
    import npc_brain

    print("[OK] npc_brain.py imported successfully.")
except Exception as e:
    print(f"[FAIL] npc_brain.py error: {e}")
    sys.exit(1)

try:
    from api import app

    print("[OK] api.py imported and app object found.")
except Exception as e:
    print(f"[FAIL] api.py error: {e}")
    sys.exit(1)

print("\nAll checks passed. Ready for Streamlit execution.")
