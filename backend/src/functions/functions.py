# ./backend/src/functions/functions.py
import os
import time
from dataclasses import dataclass
from typing import Any, List, Optional, cast

from restack_ai.function import function, log  # type: ignore

from src.baml_client.async_client import b
from src.baml_client.types import (
    GenerateCodeInput,
    GenerateCodeOutput,
    ValidateCodeInput,
    ValidateCodeOutput,
)
from src.utils.file_handling import PreFlightOutput
from src.memory_manager import add_memory, get_all_memories
from src.prompts import get_prompts


@dataclass
class RunCodeInput:
    repo_path: str
    user_id: Optional[str] = None
    run_id: Optional[str] = None


@dataclass
class PreFlightInput:
    user_id: Optional[str] = None
    run_id: Optional[str] = None


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

    # Extract user_id and run_id from activity info context
    activity_info = function.info()
    # Restack AI extends the standard Temporal info() with task_queue_context
    context = getattr(activity_info, "task_queue_context", {}) or {}
    user_id = context.get("user_id") or "anonymous"
    run_id = context.get("run_id") or str(int(time.time() * 1000))

    log.info(f"Retrieving memories for generate_code with user_id={user_id}, run_id={run_id}")
    # Get memories and cast to expected type for BAML
    memories = get_all_memories(agent_id="generate_code", run_id=run_id, user_id=user_id)
    result = await b.GenerateCode(
        input,
        systemprompt=prompts["generate_code_prompt"],
        memories=cast(Optional[List[Any]], memories),
    )

    # Convert result to string before adding to memories
    result_str = str(result)
    add_memory(result_str, agent_id="generate_code", run_id=run_id, user_id=user_id)
    return result


# RUN WITH E2B INSTEAD OF RUN LOCALLY
@function.defn()
async def run_with_e2b(input: RunCodeInput) -> RunCodeOutput:
    """
    Use E2B to build and run Docker container from files stored in MinIO.
    Returns container logs and updates files in MinIO.
    """
    # Extract user_id and run_id from activity info context
    activity_info = function.info()
    # Restack AI extends the standard Temporal info() with task_queue_context
    context = getattr(activity_info, "task_queue_context", {}) or {}
    user_id = context.get("user_id") or "anonymous"
    run_id = context.get("run_id") or str(int(time.time() * 1000))

    log.info(f"run_with_e2b => executing for user_id={user_id}, run_id={run_id}")

    # The bucket name for storing files in MinIO
    bucket_name = "azlon-files"

    # Initialize E2B functions
    from src.e2b_functions import E2BRunner

    e2b = E2BRunner()

    try:
        # Upload files from repo_path to MinIO, if they're not already there
        # This is for backwards compatibility during transition
        if hasattr(input, "repo_path") and input.repo_path:
            log.info(f"Uploading files from {input.repo_path} to MinIO")

            import os

            from src.file_server import create_bucket_if_not_exists, upload_file

            # Ensure bucket exists
            create_bucket_if_not_exists(bucket_name)

            # Upload files to MinIO under user_id/run_id prefix
            for root, _, files in os.walk(input.repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, input.repo_path)
                    object_name = f"{user_id}/{run_id}/{relative_path}"

                    upload_file(file_path, bucket_name, object_name)

            log.info(f"Uploaded files to MinIO bucket {bucket_name} with prefix {user_id}/{run_id}")

        # Run the E2B container build and execution process
        result = e2b.run_docker_container(user_id, run_id, bucket_name)

        if result["status"] == "error":
            log.error(f"E2B execution failed: {result['output']}")
            return RunCodeOutput(output=result["output"])

        # Log modified files
        if result.get("modified_files"):
            log.info(f"Files modified during execution: {result['modified_files']}")

        # Copy the directory tree for debugging
        if result.get("directory_tree"):
            output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
            user_output_dir = os.path.join(output_dir, user_id, run_id)
            os.makedirs(user_output_dir, exist_ok=True)

            with open(os.path.join(user_output_dir, "tree.txt"), "w") as f:
                f.write(result["directory_tree"])

        # Add memory record of execution
        from src.memory_manager import add_memory

        add_memory(
            {
                "type": "e2b_execution",
                "status": result["status"],
                "modified_files": result.get("modified_files", []),
            },
            agent_id="run_with_e2b",
            run_id=run_id,
            user_id=user_id,
        )

        return RunCodeOutput(output=result["output"])

    except Exception as e:
        import traceback

        error_msg = f"Error in run_with_e2b: {str(e)}\n{traceback.format_exc()}"
        log.error(error_msg)
        return RunCodeOutput(output=error_msg)


@function.defn()
async def validate_output(input: ValidateCodeInput) -> ValidateCodeOutput:
    """
    Call the BAML-based ValidateOutput function with system prompt.
    """
    log.info(f"validate_output => iteration {input.iteration}")
    prompts = get_prompts()

    # Extract user_id and run_id from activity info context
    activity_info = function.info()

    # Restack AI extends the standard Temporal info() with task_queue_context
    # Extract context data from activity info
    context = {}
    task_queue_context = getattr(activity_info, "task_queue_context", None)
    if task_queue_context:
        context = task_queue_context

    user_id = context.get("user_id") or "anonymous"
    run_id = context.get("run_id") or str(int(time.time() * 1000))
    log.info(f"Validating output for user_id={user_id}, run_id={run_id}")

    # Configure output path for any files generated
    output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    user_output_dir = os.path.join(output_dir, user_id, run_id, "validation")
    os.makedirs(user_output_dir, exist_ok=True)

    try:
        # Get memories, properly filtered by user_id and run_id
        # Get memories and cast to expected type for BAML
        memories = get_all_memories(agent_id="validate_output", run_id=run_id, user_id=user_id)

        # Log run info to file for cloud debugging
        with open(os.path.join(user_output_dir, "run_info.json"), "w") as f:
            import json

            json.dump(
                {
                    "user_id": user_id,
                    "run_id": run_id,
                    "iteration": input.iteration,
                    "timestamp": time.time(),
                    "memory_count": len(memories),
                },
                f,
                indent=2,
            )

        result = await b.ValidateOutput(
            input,
            systemprompt=prompts["validate_output_prompt"],
            memories=cast(Optional[List[Any]], memories),
        )

        # Convert result to string before adding to memories
        result_str = str(result)
        add_memory(result_str, agent_id="validate_output", run_id=run_id, user_id=user_id)

        # Save output to file for reference
        with open(os.path.join(user_output_dir, f"output_{input.iteration}.txt"), "w") as f:
            f.write(result_str)

    except Exception as e:
        log.error(f"Error in validate_output: {str(e)}")
        # Ensure we have a fallback result in case of errors
        error_message = f"Validation error: {str(e)}"
        with open(os.path.join(user_output_dir, "error.log"), "a") as f:
            f.write(f"{time.time()}: {error_message}\n")
        return ValidateCodeOutput(result=False, suspectedFiles=[], unsuspectedFiles=[])

    return result


@function.defn()
async def pre_flight_run(input: PreFlightInput) -> PreFlightOutput:
    """
    Merge user code from /input, if a Dockerfile is found then build & run once.
    Otherwise skip building.
    """
    # Extract user_id and run_id from the input object
    user_id = getattr(input, "user_id", None) or "anonymous"
    run_id = getattr(input, "run_id", None) or str(int(time.time() * 1000))

    log.info(
        f"pre_flight_run => merging user code + building container if Dockerfile is found. user_id={user_id}, run_id={run_id}"
    )

    # Configure output path for preflight files
    output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    user_output_dir = os.path.join(output_dir, user_id, run_id, "preflight")
    os.makedirs(user_output_dir, exist_ok=True)

    try:
        # Log run info to file for cloud debugging
        with open(os.path.join(user_output_dir, "preflight_start.log"), "w") as f:
            f.write(f"Starting preflight run at {time.time()}\n")
            f.write(f"User ID: {user_id}\n")
            f.write(f"Run ID: {run_id}\n")

        from src.utils.file_handling import PreFlightManager

        pfm = PreFlightManager(user_id=user_id, run_id=run_id)
        result = pfm.perform_preflight_merge_and_run()

        # Log the result
        with open(os.path.join(user_output_dir, "preflight_result.log"), "w") as f:
            f.write(f"Preflight run completed at {time.time()}\n")
            f.write(f"Directory tree:\n{result.dirTree}\n\n")
            f.write(f"Run output:\n{result.runOutput}\n")

        # Store result in memory for future reference
        add_memory(
            {"type": "preflight_result", "dirTree": result.dirTree, "runOutput": result.runOutput},
            agent_id="preflight",
            run_id=run_id,
            user_id=user_id,
        )

        return result
    except Exception as e:
        log.error(f"Error in pre_flight_run: {str(e)}")
        # Record the error
        with open(os.path.join(user_output_dir, "error.log"), "a") as f:
            f.write(f"{time.time()}: Preflight error: {str(e)}\n")
        return PreFlightOutput(
            dirTree="Error occurred during preflight run",
            runOutput=f"Preflight execution error: {str(e)}",
        )
