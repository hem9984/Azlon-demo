# ./backend/src/client.py
import os

from restack_ai import Restack  # type: ignore
from restack_ai.restack import CloudConnectionOptions  # type: ignore

RESTACK_TEMPORAL_ADDRESS = os.getenv("RESTACK_TEMPORAL_ADDRESS")
RESTACK_ENGINE_ADDRESS = os.getenv("RESTACK_ENGINE_ADDRESS")
# Use default values if environment variables are not set
RESTACK_ENGINE_ID = os.getenv("RESTACK_ENGINE_ID", "default-engine")
RESTACK_ENGINE_API_KEY = os.getenv("RESTACK_ENGINE_API_KEY")

# src/client.py
connection_options = CloudConnectionOptions(
    engine_id=RESTACK_ENGINE_ID,
    api_key=RESTACK_ENGINE_API_KEY,  # type: ignore
    address=RESTACK_TEMPORAL_ADDRESS,
    api_address=RESTACK_ENGINE_ADDRESS,
)

# Initialize Restack with production cloud options
client = Restack(connection_options)
print(f"Connected to Restack Engine: {RESTACK_ENGINE_ID} at {RESTACK_ENGINE_ADDRESS}")
