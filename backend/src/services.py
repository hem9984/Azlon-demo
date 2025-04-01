# ./backend/src/services.py
import traceback
import asyncio
import time
from src.client import client
from src.functions.functions import generate_code, run_locally, validate_output
from src.workflows.workflow import AutonomousCodingWorkflow

# Security configuration - explicitly enforce validation to address ML09 vulnerability
# This ensures all LLM-generated outputs are validated before execution
ENFORCE_VALIDATION = True  # Set to True to enforce validation, False to disable

# Create a secure wrapper for the run_locally function that ensures validation
async def secure_run_locally(code, context=None):
    """
    Secure wrapper ensuring validation before execution.
    This addresses the ML09 vulnerability by enforcing output validation
    before any generated code is executed.
    """
    # First validate the output to prevent integrity attacks
    validation_result = await validate_output(code, context)
    
    # Only proceed with execution if validation passes
    # This acts as a guardrail against potentially malicious outputs
    if validation_result:
        return await run_locally(code, context)
    else:
        print(f"Security guardrail activated - code execution blocked due to validation failure")
        return {"success": False, "error": "Execution blocked due to validation failure"}

async def main():
    try:
        # Security enhancement: Use the secure function that enforces validation
        # This ensures all code is validated before execution
        execution_function = secure_run_locally if ENFORCE_VALIDATION else run_locally
        
        await client.start_service(
            workflows=[AutonomousCodingWorkflow],
            functions=[generate_code, execution_function, validate_output],
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