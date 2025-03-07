# ./backend/main.py

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import time
import os
from typing import List, Optional
import glob
from pathlib import Path

from src.client import client
from src.prompts import get_prompts
from restack_ai import Restack

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# No global user ID - each request should include its own user ID via header or payload

class UserInput(BaseModel):
    user_prompt: str
    test_conditions: str
    user_id: Optional[str] = None

class PromptsInput(BaseModel):
    generate_code_prompt: str
    validate_output_prompt: str

# Log incoming requests with user ID if available
@app.middleware("http")
async def log_request_user_id(request: Request, call_next):
    # Get user ID from header
    user_id = request.headers.get("X-User-ID")
    if user_id:
        print(f"Processing request for user ID: {user_id}")
    
    response = await call_next(request)
    return response

@app.get("/prompts")
def fetch_prompts(x_user_id: Optional[str] = Header(None)):
    """Fetch the current prompts"""
    # Log user ID
    if x_user_id:
        print(f"Fetching prompts for user: {x_user_id}")
    return get_prompts()

# @app.post("/prompts")
# def update_prompts(prompts: PromptsInput, x_user_id: Optional[str] = Header(None)):
#     """Update the prompts"""
#     # Log user ID
#     if x_user_id:
#         print(f"Updating prompts for user: {x_user_id}")
#     set_prompts(prompts.generate_code_prompt, prompts.validate_output_prompt)
#     return {"status": "updated"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error."},
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.post("/run_workflow")
async def run_workflow(params: UserInput, x_user_id: Optional[str] = Header(None)):
    """Run the workflow with user ID"""
    # Use user ID from header or body, with fallback to 'anonymous'
    user_id = str(x_user_id or params.user_id or "anonymous")
    
    print(f"Running workflow for user: {user_id}")
    
    try:
        # Generate a unique workflow ID with user prefix
        timestamp = int(time.time() * 1000)
        workflow_id = f"user-{user_id}-{timestamp}"
        
        # Prepare workflow input with user_id included
        workflow_input = params.model_dump()
        workflow_input["user_id"] = user_id  # Ensure user_id is passed to workflow
        
        runId = await client.schedule_workflow(
            workflow_name="AutonomousCodingWorkflow",
            workflow_id=workflow_id,
            input=workflow_input
        )
        result = await client.get_workflow_result(workflow_id=workflow_id, run_id=runId)
        return {"workflow_id": workflow_id, "result": result, "user_id": user_id}
    except Exception as e:
        # If engine connection or workflow run fails, a 500 error is raised
        # The global_exception_handler ensures CORS headers are included.
        raise HTTPException(status_code=500, detail="Failed to connect to Restack engine or run workflow.")

@app.get("/output_dirs", response_model=List[str])
def list_output_dirs(x_user_id: Optional[str] = Header(None), user_id: Optional[str] = None):
    """List all final output directories, filtered by user ID if provided"""
    # Use user ID from header or query param, defaulting to 'anonymous'
    effective_user_id = x_user_id or user_id or "anonymous"
    
    if effective_user_id:
        print(f"Listing output directories for user: {effective_user_id}")
    
    base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    
    # If running locally with the path structure from the prompt
    if not os.path.exists(base_output):
        base_output = "./llm-output"
    
    # Get all directories with the "final_" prefix
    dirs = [d for d in os.listdir(base_output) 
            if os.path.isdir(os.path.join(base_output, d)) and d.startswith("final_")]
    
    # Filter by user ID if provided
    if effective_user_id:
        # Look for user ID in metadata files or directory naming convention
        user_dirs = []
        for d in dirs:
            # Check if directory name contains user ID (simple approach)
            if f"user-{effective_user_id}" in d:
                user_dirs.append(d)
            # Alternative: could check metadata files inside each directory
            
        dirs = user_dirs if user_dirs else dirs  # Fall back to all dirs if none match
    
    # Sort by name (which sorts by date since they're named with timestamps)
    dirs.sort(reverse=True)
    
    return dirs

@app.get("/output_files/{dir_name}")
def list_output_files(dir_name: str, x_user_id: Optional[str] = Header(None)):
    """List all files in a specific output directory"""
    # Log user ID
    if x_user_id:
        print(f"Listing output files for user: {x_user_id}, directory: {dir_name}")
        
    base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    
    # If running locally with the path structure from the prompt
    if not os.path.exists(base_output):
        base_output = "/Users/maximillianludwick/Desktop/POMU/Azlon-demo/llm-output"
    
    # Complete the implementation to list files in the directory
    dir_path = os.path.join(base_output, dir_name)
    
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail=f"Directory {dir_name} not found")
    
    # Walk through directory and collect files
    files = []
    for root, _, filenames in os.walk(dir_path):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, dir_path)
            files.append({
                "name": filename,
                "path": rel_path,
                "extension": os.path.splitext(filename)[1][1:] if "." in filename else ""
            })
    
    return files

@app.get("/output_file/{dir_name}/{file_path:path}")
def get_output_file(
    dir_name: str, 
    file_path: str, 
    x_user_id: Optional[str] = Header(None),
    user_id: Optional[str] = None
):
    """Get a specific file from an output directory"""
    # Use user ID from header or query param, defaulting to 'anonymous'
    effective_user_id = x_user_id or user_id or "anonymous"
    
    if effective_user_id:
        print(f"Fetching file for user: {effective_user_id}, directory: {dir_name}, file: {file_path}")
    
    base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    
    # If running locally with the path structure from the prompt
    if not os.path.exists(base_output):
        base_output = "/Users/maximillianludwick/Desktop/POMU/Azlon-demo/llm-output"
    
    file_path = os.path.join(base_output, dir_name, file_path)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found")
    
    return FileResponse(file_path)