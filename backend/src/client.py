# ./backend/src/client.py
import os

from restack_ai import Restack
from restack_ai.restack import CloudConnectionOptions

# Get environment variables with type assertions for the type checker
RESTACK_ENGINE_ID = os.getenv("RESTACK_ENGINE_ID") or ""
RESTACK_ENGINE_API_KEY = os.getenv("RESTACK_ENGINE_API_KEY") or ""
RESTACK_ENGINE_ADDRESS = os.getenv("RESTACK_ENGINE_ADDRESS") or "engine.restack.io"
RESTACK_ENGINE_API_ADDRESS = os.getenv("RESTACK_ENGINE_API_ADDRESS") or ""

# Validate required environment variables
if not RESTACK_ENGINE_ID or not RESTACK_ENGINE_API_KEY:
    print(
        "WARNING: RESTACK_ENGINE_ID or RESTACK_ENGINE_API_KEY not set. Restack workflows will not function."
    )

# src/client.py
connection_options = CloudConnectionOptions(
    engine_id=RESTACK_ENGINE_ID,
    api_key=RESTACK_ENGINE_API_KEY,
    address=RESTACK_ENGINE_ADDRESS,
    api_address=RESTACK_ENGINE_API_ADDRESS,
)

# Initialize Restack with production cloud options
client = Restack(connection_options)
print(f"Connected to Restack Engine: {RESTACK_ENGINE_ID} at {RESTACK_ENGINE_ADDRESS}")
