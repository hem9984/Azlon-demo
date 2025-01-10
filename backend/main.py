# ./backend/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import time
import os

from src.prompts import get_prompts, set_prompts
from restack_ai import Restack
from restack_ai.restack import CloudConnectionOptions

RESTACK_ENGINE_ADDRESS = os.getenv('RESTACK_ENGINE_ADDRESS')
RESTACK_TEMPORAL_ADDRESS = os.getenv('RESTACK_TEMPORAL_ADDRESS')
RESTACK_ENGINE_ID = os.getenv('RESTACK_ENGINE_ID')
RESTACK_ENGINE_API_KEY = os.getenv('RESTACK_ENGINE_API_KEY')

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:8080"],
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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error."},
        headers={"Access-Control-Allow-Origin": "http://localhost:8080"},
    )

@app.post("/run_workflow")
async def run_workflow(params: UserInput):
    connection_options = CloudConnectionOptions(
    engine_id=RESTACK_ENGINE_ID,
    api_key=RESTACK_ENGINE_API_KEY,
    address=RESTACK_TEMPORAL_ADDRESS,
    api_address=RESTACK_ENGINE_ADDRESS,
    temporal_namespace="default")

    # Initialize Restack with these options options=connection_options
    client = Restack(connection_options)
    try:
        workflow_id = f"{int(time.time() * 1000)}-AutonomousCodingWorkflow"
        runId = await client.schedule_workflow(
            workflow_name="AutonomousCodingWorkflow",
            workflow_id=workflow_id,
            input=params.dict()
        )
        result = await client.get_workflow_result(workflow_id=workflow_id, run_id=runId)
        return {"workflow_id": workflow_id, "result": result}
    except Exception as e:
        # If engine connection or workflow run fails, a 500 error is raised
        # The global_exception_handler ensures CORS headers are included.
        raise HTTPException(status_code=500, detail="Failed to connect to Restack engine or run workflow.")
