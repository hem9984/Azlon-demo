# ./backend/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from restack_ai import Restack
import time
from fastapi.responses import JSONResponse

from src.prompts import get_prompts, set_prompts

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or "*" if you prefer
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

# Exception handler to ensure CORS headers are present even on errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the error if needed
    # For security, you might want to return a generic message instead of str(exc)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
        headers={"Access-Control-Allow-Origin": "http://localhost:3000"},
    )

@app.post("/run_workflow")
async def run_workflow(params: UserInput):
    # Attempt to connect to the Restack engine on the known ports.
    # According to your run command, ports are mapped:
    # 5233 - Restack GUI
    # 6233 - Possibly workflow RPC
    # 7233 - Possibly Temporal or another internal service
    # We'll try 6233 first.

    # Inside Docker, use the service name "restack-engine" if defined in docker-compose
    # If your service is named 'restack-engine', do: host="restack-engine"
    # If it's named just 'restack', do: host="restack"
    # We'll assume service name is 'restack-engine' as per your docker-compose

    host = "restack-engine"  # If your docker-compose service is named "restack-engine", use that name. For now let's use "restack" since you named the container restack.
    # If container_name doesn't define the network alias, set in docker-compose:
    # services:
    #   restack-engine:
    #     container_name: restack
    #     ...
    # Then host="restack" works

    # If engine not accessible via 'restack', try 'restack-engine'.
    # host = "restack-engine"

    port = 6233  # Attempt with 6233 first

    try:
        client = Restack(host=host, port=port)
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
        # If connection fails, you can try another port or raise an HTTPException.
        # Try 7233 if 6233 fails:
        try:
            client = Restack(host=host, port=7233)
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
        except Exception as e2:
            # If still fails, raise a 500 error
            raise HTTPException(status_code=500, detail="Failed to connect to Restack engine on both ports.")
