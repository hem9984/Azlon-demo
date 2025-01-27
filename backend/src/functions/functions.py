#./backend/src/functions/functions.py
from restack_ai.function import function, log
from dataclasses import dataclass
import os
import openai
import json
import subprocess
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from src.prompts import current_generate_code_prompt, current_validate_output_prompt
from src.utils.file_handling import (
    run_tree_command,
    initialize_git_repo,
    prepare_codebase_merge,
    collect_input_files,
    build_files_str  # <--- new utility for partial vs. full
)

openai.api_key = os.environ.get("OPENAI_KEY")
from openai import OpenAI
client = OpenAI(api_key=openai.api_key)

class FileItem(BaseModel):
    filename: str
    content: str

    class Config:
        extra = "forbid"
        schema_extra = {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["filename", "content"],
            "additionalProperties": False
        }

class GenerateCodeSchema(BaseModel):
    dockerfile: str
    files: List[FileItem]
    
    class Config:
        extra = "forbid"
        schema_extra = {
            "type": "object",
            "properties": {
                "dockerfile": {"type": "string"},
                "files": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/FileItem"}
                }
            },
            "required": ["dockerfile", "files"],
            "additionalProperties": False,
            "$defs": {
                "FileItem": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["filename", "content"],
                    "additionalProperties": False
                }
            }
        }

class ValidateOutputSchema(BaseModel):
    result: bool
    dockerfile: Optional[str] = None
    files: Optional[List[FileItem]] = None
    
    class Config:
        extra = "forbid"
        schema_extra = {
            "type": "object",
            "properties": {
                "result": {"type": "boolean"},
                "dockerfile": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ]
                },
                "files": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {"$ref": "#/$defs/FileItem"}
                        },
                        {"type": "null"}
                    ]
                }
            },
            "required": ["result", "dockerfile", "files"],
            "additionalProperties": False,
            "$defs": {
                "FileItem": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["filename", "content"],
                    "additionalProperties": False
                }
            }
        }

@dataclass
class GenerateCodeInput:
    user_prompt: str
    test_conditions: str

@dataclass
class GenerateCodeOutput:
    dockerfile: str
    files: list

@dataclass
class RunCodeInput:
    dockerfile: str
    files: list

@dataclass
class RunCodeOutput:
    output: str

@dataclass
class ValidateOutputInput:
    dockerfile: str
    files: list
    output: str
    test_conditions: str
    iteration: int  # <--- new field to indicate iteration index

@dataclass
class ValidateOutputOutput:
    result: bool
    dockerfile: Optional[str] = None
    files: Optional[list] = None

#
# 1) generate_code
#
@function.defn()
async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
    log.info("generate_code started", input=input)

    prompt = current_generate_code_prompt.format(
        user_prompt=input.user_prompt,
        test_conditions=input.test_conditions
    )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system",
                "content": "You are the initial of an autonomous coding assistant agent. Generate complete code that will run."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format=GenerateCodeSchema
    )

    result = completion.choices[0].message
    if result.refusal:
        raise RuntimeError("Model refused to generate code.")
    data = result.parsed

    files_list = [{"filename": f.filename, "content": f.content} for f in data.files]

    return GenerateCodeOutput(dockerfile=data.dockerfile, files=files_list)

#
# 2) run_locally
#
@function.defn()
async def run_locally(input: RunCodeInput) -> RunCodeOutput:
    log.info("run_locally started", input=input)
    
    base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(base_output_dir, f"llm_run_{timestamp}")
    os.makedirs(run_folder, exist_ok=True)
    
    # Write Dockerfile
    dockerfile_path = os.path.join(run_folder, "Dockerfile")
    os.makedirs(os.path.dirname(dockerfile_path), exist_ok=True)
    with open(dockerfile_path, "w", encoding="utf-8") as f:
        f.write(input.dockerfile)
    log.info(f"Wrote Dockerfile to {dockerfile_path}")

    # Initialize Git for merging
    initialize_git_repo(run_folder)
    subprocess.run(["git", "add", "-A"], cwd=run_folder, check=True)
    subprocess.run(["git", "commit", "-m", "Initial Dockerfile commit"], cwd=run_folder, check=True)

    # Merge in the LLM's new files
    prepare_codebase_merge(
        repo_path=run_folder,
        llm_files=input.files
    )

    # Show tree for debugging
    tree_output = run_tree_command(run_folder)
    log.info(f"Directory after merge:\n{tree_output}")

    # Docker build
    build_cmd = ["docker", "build", "-t", "myapp", run_folder]
    build_process = subprocess.run(build_cmd, capture_output=True, text=True)
    if build_process.returncode != 0:
        return RunCodeOutput(output=build_process.stderr or build_process.stdout)
    
    # Docker run
    run_cmd = ["docker", "run", "--rm", "myapp"]
    run_process = subprocess.run(run_cmd, capture_output=True, text=True)
    if run_process.returncode != 0:
        return RunCodeOutput(output=run_process.stderr or run_process.stdout)
    
    return RunCodeOutput(output=run_process.stdout)

#
# 3) validate_output
#
@function.defn()
async def validate_output(input: ValidateOutputInput) -> ValidateOutputOutput:
    log.info("validate_output started", input=input)

    # Build partial or full code listing depending on iteration
    files_str = build_files_str(
        dockerfile=input.dockerfile,
        files=input.files,
        iteration=input.iteration
    )

    validation_prompt = current_validate_output_prompt.format(
        test_conditions=input.test_conditions,
        dockerfile=input.dockerfile,
        files_str=files_str,
        output=input.output
    )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system",
                "content": "You are an iteration of an autonomous coding assistant agent. If you change any files, provide complete file content replacements. Append a brief explanation at the bottom of readme.md about what you tried."
            },
            {
                "role": "user",
                "content": validation_prompt
            }
        ],
        response_format=ValidateOutputSchema
    )

    result = completion.choices[0].message
    if result.refusal:
        return ValidateOutputOutput(result=False)

    data = result.parsed
    updated_files = [{"filename": f.filename, "content": f.content} for f in data.files] if data.files is not None else None

    return ValidateOutputOutput(
        result=data.result,
        dockerfile=data.dockerfile,
        files=updated_files
    )

#
# 4) pre_flight_run
#
@dataclass
class PreFlightOutput:
    dir_tree: str
    run_output: str

@function.defn()
async def pre_flight_run() -> PreFlightOutput:
    """
    1. Gather user code from ./llm-output/input
    2. If no Dockerfile among user code, create a minimal one
    3. Merge + run in Docker
    4. Return container output + final directory tree
    """
    log.info("pre_flight_run started")

    base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(base_output_dir, f"preflight_{timestamp}")
    os.makedirs(run_folder, exist_ok=True)

    # 1) Collect user code
    user_json = collect_input_files()
    if not user_json["dockerfile"].strip():
        default_dockerfile = """FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y python3 python3-pip
ENTRYPOINT ["python3","main.py"]
"""
        user_json["dockerfile"] = default_dockerfile

    # 2) Initialize Git + commit Dockerfile
    dockerfile_path = os.path.join(run_folder, "Dockerfile")
    with open(dockerfile_path, "w", encoding="utf-8") as df:
        df.write(user_json["dockerfile"])

    initialize_git_repo(run_folder)
    subprocess.run(["git", "add", "-A"], cwd=run_folder, check=True)
    subprocess.run(["git", "commit", "-m", "pre-flight base Dockerfile"], cwd=run_folder, check=True)

    # 3) Merge user files
    prepare_codebase_merge(
        repo_path=run_folder,
        llm_files=user_json["files"]
    )

    # 4) Build & run
    build_cmd = ["docker", "build", "-t", "preflight_app", run_folder]
    build_process = subprocess.run(build_cmd, capture_output=True, text=True)
    if build_process.returncode != 0:
        dir_tree = run_tree_command(run_folder)
        return PreFlightOutput(
            dir_tree=dir_tree,
            run_output=(build_process.stderr or build_process.stdout)
        )

    run_cmd = ["docker", "run", "--rm", "preflight_app"]
    run_process = subprocess.run(run_cmd, capture_output=True, text=True)
    dir_tree = run_tree_command(run_folder)
    if run_process.returncode != 0:
        return PreFlightOutput(dir_tree=dir_tree, run_output=(run_process.stderr or run_process.stdout))

    return PreFlightOutput(dir_tree=dir_tree, run_output=run_process.stdout)
