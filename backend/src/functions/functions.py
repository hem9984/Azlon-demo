#./backend/src/functions/functions.py
from restack_ai.function import function, log
from dataclasses import dataclass
import os
import openai
import subprocess
from datetime import datetime
from typing import List

from pydantic import BaseModel

from src.prompts import current_generate_code_prompt, current_validate_output_prompt
from src.utils.file_handling import (
    run_tree_command,
    initialize_git_repo,
    prepare_codebase_merge,
    collect_input_files,
    build_files_str
)
from src.baml_client.async_client import b
from src.baml_client.types import GenerateCodeInput, GenerateCodeOutput, PreFlightOutput
from src.baml_client.types import ValidateCodeInput, ValidateCodeOutput

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

@dataclass
class RunCodeInput:
    dockerfile: str
    files: list

@dataclass
class RunCodeOutput:
    output: str

#
# generate_code
#
@function.defn()
async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
    log.info("generate_code started", input=input)
    result = await b.GenerateCode(input, systemprompt=current_generate_code_prompt)
    return result

#
# run_locally
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

    # Initialize Git
    initialize_git_repo(run_folder)
    # We'll allow empty commit in case there's nothing else to add
    commit_cmd = ["git", "add", "-A"]
    subprocess.run(commit_cmd, cwd=run_folder, check=True)
    commit_cmd = ["git", "commit", "-m", "Initial Dockerfile commit", "--allow-empty"]
    subprocess.run(commit_cmd, cwd=run_folder, check=True)

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
# validate_output
#
@function.defn()
async def validate_output(input: ValidateCodeInput) -> ValidateCodeOutput:
    log.info("validate_output started", input=input)
    result = await b.ValidateOutput(input, systemprompt=current_validate_output_prompt)
    return result

#
# pre_flight_run
#
@function.defn()
async def pre_flight_run() -> PreFlightOutput:
    log.info("pre_flight_run started")

    base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(base_output_dir, f"preflight_{timestamp}")
    os.makedirs(run_folder, exist_ok=True)

    user_json = collect_input_files()
    if not user_json["dockerfile"].strip():
        default_dockerfile = """FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y python3 python3-pip
ENTRYPOINT ["python3","main.py"]
"""
        user_json["dockerfile"] = default_dockerfile

    dockerfile_path = os.path.join(run_folder, "Dockerfile")
    with open(dockerfile_path, "w", encoding="utf-8") as df:
        df.write(user_json["dockerfile"])

    initialize_git_repo(run_folder)
    subprocess.run(["git", "add", "-A"], cwd=run_folder, check=True)
    # allow empty commit
    subprocess.run(["git", "commit", "-m", "pre-flight base Dockerfile", "--allow-empty"], cwd=run_folder, check=True)

    # Merge user files
    prepare_codebase_merge(
        repo_path=run_folder,
        llm_files=user_json["files"]
    )

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
