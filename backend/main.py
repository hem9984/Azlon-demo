# ./backend/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import time
import os

# Import Restack and connection options
from restack_ai import Restack
from restack_ai.restack import CloudConnectionOptions

from src.prompts import get_prompts, set_prompts

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Match your frontend exactly
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
    # For security and cleanliness, don't expose internal details in production
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error. Check logs for details."},
        headers={"Access-Control-Allow-Origin": "http://localhost:3000"},
    )

@app.post("/run_workflow")
async def run_workflow(params: UserInput):
    # According to your docker run, ports are mapped, and inside docker network:
    # restack-engine:6233 should be accessible.
    # We will attempt to connect directly with connection options.
    
    connection_options = CloudConnectionOptions(
        address="restack-engine:6233"
        # no engine_id or api_key since running locally
    )
    client = Restack(connection_options=connection_options)

    try:
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
        # If it fails here, it likely couldn't connect or failed inside Restack.
        # The global_exception_handler will ensure CORS headers.
        raise HTTPException(status_code=500, detail="Failed to connect to Restack engine or run workflow.")
