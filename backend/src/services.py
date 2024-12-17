# src/services.py
import asyncio
from src.client import client
from src.functions.functions import generate_code, run_locally, validate_output
from src.workflows.workflow import AutonomousCodingWorkflow

async def main():
    await client.start_service(
        workflows=[AutonomousCodingWorkflow],
        functions=[generate_code, run_locally, validate_output],
    )

def run_services():
    asyncio.run(main())

if __name__ == "__main__":
    run_services()
