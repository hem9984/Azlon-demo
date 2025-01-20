# backend/src/services.py
import traceback
import asyncio
import time
from src.client import client
from src.functions.functions import generate_code, run_locally, validate_output
from src.workflows.workflow import AutonomousCodingWorkflow

async def main():
    try:
        await client.start_service(
            workflows=[AutonomousCodingWorkflow],
            functions=[generate_code, run_locally, validate_output],
        )
    except Exception as e:
        print(f"Error starting service: traceback: {traceback.format_exc()}")
        print(f"Error starting service: {e}")
        raise

def run_services():
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Service failed: {e}")
    # Keep the process alive for inspection
    while True:
        time.sleep(1)

if __name__ == "__main__":
    run_services()