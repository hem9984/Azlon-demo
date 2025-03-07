# backend/schedule_workflow.py
import asyncio
import time
from dataclasses import asdict
from src.client import client

async def main():
    # Use a consistent user_id for testing
    user_id = "simple_test"
    timestamp = int(time.time() * 1000)
    
    # Create a properly formatted workflow_id with user_id prefix
    workflow_id = f"user-{user_id}-{timestamp}"
    
    # Prepare the input payload with user_id included
    workflow_input = {
        "user_prompt": "Write a python script that prints 'hello world'",
        "test_conditions": "The script must print exactly 'hello world'",
        "user_id": user_id  # Important: Include user_id in the input
    }
    
    print(f"Scheduling test workflow for user: {user_id}")
    print(f"Workflow ID: {workflow_id}")
    
    # Schedule the workflow
    run_id = await client.schedule_workflow(
        workflow_name="AutonomousCodingWorkflow",
        workflow_id=workflow_id,
        input=workflow_input
    )
    
    print(f"Workflow scheduled with run ID: {run_id}")
    print("Waiting for workflow completion...")
    
    # Wait for workflow result
    result = await client.get_workflow_result(
        workflow_id=workflow_id,
        run_id=run_id
    )
    
    print("\nWorkflow completed successfully!")
    print(f"Result: {result}")

def run_schedule_workflow():
    asyncio.run(main())

if __name__ == "__main__":
    run_schedule_workflow()
