# ./backend/src/functions/functions.py
from restack_ai.function import function, log  # type: ignore
from dataclasses import dataclass
import subprocess

from src.baml_client.async_client import b 
from src.baml_client.types import ( 
    GenerateCodeInput, GenerateCodeOutput,
    ValidateCodeInput, ValidateCodeOutput,
    PreFlightOutput
)
from src.prompts import get_prompts

@dataclass
class RunCodeInput:
    repo_path: str

@dataclass
class RunCodeOutput:
    output: str

@function.defn()
async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
    """
    Call the BAML-based GenerateCode function with system prompt
    to produce a Dockerfile and code files.
    """
    log.info(f"generate_code started => {input}")
    prompts = get_prompts()
    # when i update prompts in frontend, it does not actually update the prompts from the default
    result = await b.GenerateCode(input, systemprompt=prompts["generate_code_prompt"])
    return result

@function.defn()
async def run_locally(input: RunCodeInput) -> RunCodeOutput:
    """
    Docker build & run from ephemeral workspace. 
    Return logs if build/run fails.
    """
    log.info(f"run_locally => building in {input.repo_path}")
    build_cmd = ["docker", "build", "-t", "myapp", input.repo_path]
    proc_build = subprocess.run(build_cmd, capture_output=True, text=True)
    if proc_build.returncode != 0:
        return RunCodeOutput(output=proc_build.stderr or proc_build.stdout)

    run_cmd = [
        "docker", "run", "--rm",
        "-v", f"{input.repo_path}:/app",
        "myapp"
    ]
    proc_run = subprocess.run(run_cmd, capture_output=True, text=True)
    if proc_run.returncode != 0:
        return RunCodeOutput(output=proc_run.stderr or proc_run.stdout)

    return RunCodeOutput(output=proc_run.stdout)

@function.defn()
async def validate_output(input: ValidateCodeInput) -> ValidateCodeOutput:
    """
    Call the BAML-based ValidateOutput function with system prompt.
    """
    log.info(f"validate_output => iteration {input.iteration}")
    prompts = get_prompts()
    result = await b.ValidateOutput(input, systemprompt=prompts["validate_output_prompt"])
    return result

@function.defn()
async def pre_flight_run() -> PreFlightOutput:
    """
    Merge user code from /input, if a Dockerfile is found then build & run once.
    Otherwise skip building.
    """
    log.info("pre_flight_run => merging user code + building container if Dockerfile is found.")
    from src.utils.file_handling import PreFlightManager
    pfm = PreFlightManager()
    return pfm.perform_preflight_merge_and_run()
