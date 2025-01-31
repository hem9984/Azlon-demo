#./backend/src/functions/functions.py
from restack_ai.function import function, log
from dataclasses import dataclass
import os
import subprocess
from datetime import datetime

from src.baml_client.types import (
    GenerateCodeInput, GenerateCodeOutput,
    ValidateCodeInput, ValidateCodeOutput,
    PreFlightOutput
)
from typing import List
from src.prompts import current_generate_code_prompt, current_validate_output_prompt
from src.baml_client.async_client import b

@dataclass
class RunCodeInput:
    repo_path: str  # ephemeral workspace path on disk

@dataclass
class RunCodeOutput:
    output: str

@function.defn()
async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
    """
    Calls your BAML 'GenerateCode' function with an optional system prompt.
    """
    log.info("generate_code started", input=input)
    result = await b.GenerateCode(input, systemprompt=current_generate_code_prompt)
    return result

@function.defn()
async def run_locally(input: RunCodeInput) -> RunCodeOutput:
    """
    Builds & runs Docker from 'repo_path'. We attach a volume so that any 
    file created inside the container is reflected on the host.
    """
    # Use a single string argument for log.info:
    log.info(f"run_locally started: building & running Docker in {input.repo_path}")

    repo_path = input.repo_path

    # 1) Docker build
    build_cmd = ["docker", "build", "-t", "myapp", repo_path]
    build_proc = subprocess.run(build_cmd, capture_output=True, text=True)
    if build_proc.returncode != 0:
        return RunCodeOutput(output=build_proc.stderr or build_proc.stdout)

    # 2) Docker run => mount volume from the ephemeral workspace
    run_cmd = [
        "docker", "run", "--rm",
        "-v", f"{repo_path}:/app",  # mount workspace at /app
        "myapp"
    ]
    run_proc = subprocess.run(run_cmd, capture_output=True, text=True)
    if run_proc.returncode != 0:
        return RunCodeOutput(output=run_proc.stderr or run_proc.stdout)

    return RunCodeOutput(output=run_proc.stdout)


@function.defn()
async def validate_output(input: ValidateCodeInput) -> ValidateCodeOutput:
    """
    Calls your BAML 'ValidateOutput' function with an optional system prompt.
    """
    log.info("validate_output started", input=input)
    result = await b.ValidateOutput(input, systemprompt=current_validate_output_prompt)
    return result

@function.defn()
async def pre_flight_run() -> PreFlightOutput:
    """
    Merges user code from input/ into ephemeral folder, builds & runs Docker.
    """
    log.info("pre_flight_run started")
    from src.utils.file_handling import PreFlightManager
    pm = PreFlightManager()
    return pm.perform_preflight_merge_and_run()
