# ./backend/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from restack_ai import Restack
import time
import asyncio

from src.prompts import get_prompts, set_prompts

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
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

@app.post("/run_workflow")
async def run_workflow(params: UserInput):
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
