import os 
from restack_ai import Restack
from restack_ai.restack import CloudConnectionOptions

RESTACK_TEMPORAL_ADDRESS = os.getenv('RESTACK_TEMPORAL_ADDRESS')
RESTACK_ENGINE_ADDRESS = os.getenv('RESTACK_ENGINE_ADDRESS')
RESTACK_ENGINE_ID = os.getenv('RESTACK_ENGINE_ID')
RESTACK_ENGINE_API_KEY = os.getenv('RESTACK_ENGINE_API_KEY')

# src/client.py
connection_options = CloudConnectionOptions(
    engine_id=RESTACK_ENGINE_ID,
    api_key=RESTACK_ENGINE_API_KEY,
    address=RESTACK_TEMPORAL_ADDRESS,
    api_address=RESTACK_ENGINE_ADDRESS,
    temporal_namespace="default")

# Initialize Restack with these options options=connection_options
client = Restack(connection_options)