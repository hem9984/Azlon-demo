# ./backend/src/services.py
import traceback
import asyncio
import time
import logging
import os
from src.client import client
from src.functions.functions import generate_code, run_locally, validate_output
from src.workflows.workflow import AutonomousCodingWorkflow

# Set up basic logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

async def main():
    try:
        await client.start_service(
            workflows=[AutonomousCodingWorkflow],
            functions=[generate_code, run_locally, validate_output],
        )
    except Exception as e:
        # Log the detailed traceback
        logger.error("Error starting service:", exc_info=True)
        
        # In development environments, you might want to see the traceback
        if os.environ.get('DEBUG') == 'true':
            print(f"Error starting service: traceback: {traceback.format_exc()}")
        else:
            # In production, only show a generic message
            print(f"Error starting service: {e}")
        
        raise

def run_services():
    try:
        asyncio.run(main())
    except Exception as e:
        # Log the detailed error
        logger.error("Service failed:", exc_info=True)
        
        # Simple error message for users
        print(f"Service failed: {e}")
    
    # Keep the process alive for inspection
    while True:
        time.sleep(1)

if __name__ == "__main__":
    run_services()