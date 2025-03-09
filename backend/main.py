# ./backend/main.py

from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response, StreamingResponse
from pydantic import BaseModel
import time
import os
import io
from typing import List, Optional, Union, Dict, Any
import glob
from pathlib import Path

from src.client import client
from src.prompts import get_prompts
from restack_ai import Restack

# Import file handling functions
from src.file_server import (
    create_workflow_zip,
    get_workflow_files,
    download_file,
    upload_file,
    extract_and_upload_zip,
    list_files,
    create_bucket_if_not_exists
)

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


@app.get("/workflow_result/{user_id}/{workflow_id}")
async def get_workflow_result(user_id: str, workflow_id: str, x_user_id: Optional[str] = Header(None)):
    """
    Get workflow result files using S3/MinIO
    This endpoint replaces the backwards compatible endpoints (output_dirs, output_files, output_file)
    """
    # Use user ID from path param or header, defaulting to path param
    effective_user_id = user_id or x_user_id or "anonymous"
    
    print(f"Fetching workflow results for user: {effective_user_id}, workflow ID: {workflow_id}")
    
    # Create bucket if it doesn't exist
    bucket_name = os.environ.get("MINIO_BUCKET_NAME", "azlon-files")
    create_bucket_if_not_exists(bucket_name)
    
    # Get files from MinIO
    files = get_workflow_files(bucket_name, effective_user_id, workflow_id)
    
    # Format the response to match the existing output_files endpoint
    formatted_files = []
    for file_info in files:
        key = file_info.get("key", "")
        filename = key.split("/")[-1] if "/" in key else key
        extension = os.path.splitext(filename)[1][1:] if "." in filename else ""
        
        formatted_files.append({
            "name": filename,
            "path": key,  # Full path as S3 key
            "extension": extension,
            "size": file_info.get("size", 0)
        })
    
    return formatted_files


@app.get("/workflow_file/{user_id}/{workflow_id}/{file_path:path}")
async def get_workflow_file(
    user_id: str,
    workflow_id: str,
    file_path: str,
    x_user_id: Optional[str] = Header(None)
):
    """
    Get a specific file from a workflow using S3/MinIO
    Equivalent to the output_file endpoint but uses MinIO storage
    """
    # Use user ID from path param or header, defaulting to path param
    effective_user_id = user_id or x_user_id or "anonymous"
    
    print(f"Fetching file for user: {effective_user_id}, workflow ID: {workflow_id}, file: {file_path}")
    
    # Define bucket and object key
    bucket_name = os.environ.get("MINIO_BUCKET_NAME", "azlon-files")
    object_key = f"user-{effective_user_id}/{workflow_id}/{file_path}"
    
    # Download file content from MinIO
    file_content = download_file(bucket_name, object_key)
    
    if not file_content:
        raise HTTPException(status_code=404, detail=f"File not found")
    
    # Return file with appropriate content type
    filename = os.path.basename(file_path)
    content_type = "application/octet-stream"
    
    # Set content type based on file extension
    extension = os.path.splitext(filename)[1].lower()
    if extension in [".txt", ".md"]:
        content_type = "text/plain"
    elif extension == ".json":
        content_type = "application/json"
    elif extension == ".html":
        content_type = "text/html"
    elif extension == ".css":
        content_type = "text/css"
    elif extension == ".js":
        content_type = "application/javascript"
    elif extension in [".png", ".jpg", ".jpeg", ".gif"]:
        content_type = f"image/{extension[1:]}"
    
    return Response(content=file_content, media_type=content_type, headers={"Content-Disposition": f"inline; filename={filename}"})


@app.get("/workflow_zip/{user_id}/{workflow_id}")
async def download_workflow_zip(
    user_id: str,
    workflow_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """
    Download all files from a workflow as a zip file
    """
    # Use user ID from path param or header, defaulting to path param
    effective_user_id = user_id or x_user_id or "anonymous"
    
    print(f"Creating zip for user: {effective_user_id}, workflow ID: {workflow_id}")
    
    # Define bucket
    bucket_name = os.environ.get("MINIO_BUCKET_NAME", "azlon-files")
    
    # Create zip file in memory
    zip_content, zip_filename = create_workflow_zip(bucket_name, effective_user_id, workflow_id)
    
    if not zip_content or not zip_filename:
        raise HTTPException(status_code=404, detail=f"No files found for workflow {workflow_id}")
    
    # Return zip file for download
    return StreamingResponse(
        io.BytesIO(zip_content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={zip_filename}"
        }
    )


@app.post("/upload_input/{user_id}")
async def upload_input_files(
    user_id: str,
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None)
):
    """
    Upload input files for a workflow
    Handles both regular files and zip files
    """
    # Use user ID from path param or header, defaulting to path param
    effective_user_id = user_id or x_user_id or "anonymous"
    
    print(f"Uploading input files for user: {effective_user_id}")
    
    # Define bucket
    bucket_name = os.environ.get("MINIO_BUCKET_NAME", "azlon-files")
    create_bucket_if_not_exists(bucket_name)
    
    # Read file content
    file_content = await file.read()
    filename = file.filename or "unnamed_file"
    content_type = file.content_type or "application/octet-stream"
    
    uploaded_files = []
    
    # Check if the file is a zip file
    if filename and filename.lower().endswith(".zip") or content_type == "application/zip":
        # Handle zip file - extract and upload all files
        uploaded_files = extract_and_upload_zip(bucket_name, effective_user_id, file_content)
    else:
        # Handle regular file - upload directly
        object_key = f"input/{effective_user_id}/{filename}"
        
        if upload_file(file_content, bucket_name, object_key):
            uploaded_files = [{
                "filename": filename,
                "size": len(file_content),
                "key": object_key
            }]
    
    if not uploaded_files:
        raise HTTPException(status_code=500, detail="Failed to upload files")
    
    return {
        "message": "Files uploaded successfully",
        "files": uploaded_files
    }