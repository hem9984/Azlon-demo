# ./backend/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import time
import os

from src.prompts import get_prompts, set_prompts

# We assume local dev mode for Restack
# If RESTACK_ENGINE_ADDRESS is set, Restack uses it for local dev.
from restack_ai import Restack

app = FastAPI()

# CORS configuration: allow from your frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class UserInput(BaseModel):
    user_prompt: str
    test_conditions: str

class PromptsInput(BaseModel):
    generate_code_prompt: str
    validate_output_prompt: str

@app.get("/prompts")
def fetch_prompts():
    return get_prompts()

@app.post("/prompts")
def update_prompts(prompts: PromptsInput):
    set_prompts(prompts.generate_code_prompt, prompts.validate_output_prompt)
    return {"status": "updated"}

# Exception handler to ensure CORS headers on errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # For security, return a generic message
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error."},
        headers={"Access-Control-Allow-Origin": "http://localhost:3000"},
    )

@app.post("/run_workflow")
async def run_workflow(params: UserInput):
    # In local dev mode, Restack tries RESTACK_ENGINE_ADDRESS if set.
    # Ensure RESTACK_ENGINE_ADDRESS=http://restack:6233 is set in docker-compose environment.

    try:
        # No arguments means local dev mode using RESTACK_ENGINE_ADDRESS
        client = Restack()
        workflow_id = f"{int(time.time() * 1000)}-AutonomousCodingWorkflow"
        runId = await client.schedule_workflow(
            workflow_name="AutonomousCodingWorkflow",
            workflow_id=workflow_id,
            input=params
        )
        result = await client.get_workflow_result(
            workflow_id=workflow_id,
            run_id=runId
        )
        return {"workflow_id": workflow_id, "result": result}
    except Exception as e:
        # Return a 500 error on failure, the global_exception_handler adds CORS
        raise HTTPException(status_code=500, detail="Failed to connect to Restack engine or run workflow.")
