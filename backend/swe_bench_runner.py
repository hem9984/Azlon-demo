# ./backend/swe_bench_runner.py

import os
import json
import time
import pathlib
import jsonlines
import asyncio
from dataclasses import dataclass
from restack_ai import Restack
from restack_ai.restack import CloudConnectionOptions

# We'll reuse your workflow
from src.workflows.workflow import AutonomousCodingWorkflow

# Path to your local swe-bench fork
SWE_BENCH_BASE = "/home/harrison/experiments"
# Our submission folder per SWE-bench instructions
SUBMISSION_DATE_MODEL = "20250110_Azlon_gpt4o"
SUBMISSION_DIR = os.path.join(SWE_BENCH_BASE, "evaluation", "verified", SUBMISSION_DATE_MODEL)
LOGS_DIR = os.path.join(SUBMISSION_DIR, "logs")
TRAJS_DIR = os.path.join(SUBMISSION_DIR, "trajs")
ALL_PREDS_FILE = os.path.join(SUBMISSION_DIR, "all_preds.jsonl")

# Ensure directories exist
pathlib.Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
pathlib.Path(TRAJS_DIR).mkdir(parents=True, exist_ok=True)

# We'll store final predictions in memory, then write to all_preds.jsonl
all_preds = []

@dataclass
class SweTask:
    task_id: str
    user_prompt: str
    test_conditions: str

async def run_task(task: SweTask):
    """
    Schedules and runs the AutonomousCodingWorkflow for a single task.
    Returns final patch, iteration logs, success/failure, etc.
    """
    # Prepare a client connection (adjust addresses if needed)
    connection_options = CloudConnectionOptions(
        engine_id="local",
        api_key=None,
        address=os.getenv("RESTACK_TEMPORAL_ADDRESS", "localhost:7233"),
        api_address=os.getenv("RESTACK_ENGINE_ADDRESS", "localhost:6233"),
        temporal_namespace="default"
    )
    client = Restack(connection_options)

    workflow_id = f"{task.task_id}-{int(time.time()*1000)}"
    run_id = await client.schedule_workflow(
        workflow_name="AutonomousCodingWorkflow",
        workflow_id=workflow_id,
        input={
            "user_prompt": task.user_prompt,
            "test_conditions": task.test_conditions
        }
    )
    result = await client.get_workflow_result(workflow_id=workflow_id, run_id=run_id)
    return result

def write_artifacts(task: SweTask, result: dict):
    """
    Write out patch.diff, run_instance.log, report.json, test_output.txt,
    trajs/<task_id>.md, plus store a single line in all_preds.jsonl
    """
    task_logs_dir = os.path.join(LOGS_DIR, task.task_id)
    pathlib.Path(task_logs_dir).mkdir(exist_ok=True)

    # patch.diff
    patch_diff_path = os.path.join(task_logs_dir, "patch.diff")
    with open(patch_diff_path, "w") as f:
        f.write(result["patch"] if result["patch"] else "")

    # Minimal: We'll create a report.json
    report_data = {
        "task_id": task.task_id,
        "resolved": result["success"]
    }
    with open(os.path.join(task_logs_dir, "report.json"), "w") as f:
        json.dump(report_data, f, indent=2)

    # run_instance.log – store some debug info (like the entire steps array)
    run_log_path = os.path.join(task_logs_dir, "run_instance.log")
    with open(run_log_path, "w") as f:
        f.write("Workflow steps:\n")
        for step in result["steps"]:
            f.write(f"Iteration {step['iteration']}:\n")
            f.write(f"- Dockerfile before:\n{step['dockerfile_before']}\n")
            f.write(f"- run_output:\n{step['run_output']}\n")
            f.write(f"- validate_result: {step['validate_result']}\n\n")

    # test_output.txt – placeholder for test run logs. We assume “docker run” output is in step["run_output"].
    test_output_path = os.path.join(task_logs_dir, "test_output.txt")
    with open(test_output_path, "w") as f:
        # For now, just dump the final run output
        if result["steps"]:
            last_step = result["steps"][-1]
            f.write(last_step["run_output"])
        else:
            f.write("No steps recorded")

    # Create a reasoning trace in trajs/<task_id>.md
    trace_path = os.path.join(TRAJS_DIR, f"{task.task_id}.md")
    with open(trace_path, "w") as f:
        f.write(f"# Reasoning Trace for {task.task_id}\n\n")
        for step in result["steps"]:
            f.write(f"**Iteration {step['iteration']}**\n\n")
            f.write(f"Run Output:\n{step['run_output']}\n\n")
            f.write(f"Validate Result: {step['validate_result']}\n\n---\n\n")

    # Finally, append to all_preds.jsonl
    final_patch = result["patch"] or ""
    all_preds.append({
        "task_id": task.task_id,
        "output": final_patch
    })

async def main():
    # Example single or multiple tasks. 
    # (In real usage, you'd load from a JSONL or your UI to get 2000+ tasks.)
    tasks = [
        SweTask(
            task_id="astropy__astropy-1234",
            user_prompt="Fix a bug in WCS handling with non-linear distortions",
            test_conditions="The code must run without errors in Docker and produce correct WCS transformations."
        ),
        SweTask(
            task_id="astropy__astropy-5678",
            user_prompt="Ensure the code prints 'Hello Universe' to stdout",
            test_conditions="Docker container must print 'Hello Universe' and exit with code 0."
        )
    ]

    for t in tasks:
        print(f"Running {t.task_id} ...")
        result = await run_task(t)
        write_artifacts(t, result)

    # Write all_preds.jsonl
    with jsonlines.open(ALL_PREDS_FILE, mode="w") as writer:
        writer.write_all(all_preds)

    # Also create minimal metadata.yaml + README.md in SUBMISSION_DIR
    metadata = {
        "name": "Azlon GPT4o",
        "oss": False,        # set to True if open-source
        "site": "https://example.com/azlon-gpt4o",
        "verified": False
    }
    with open(os.path.join(SUBMISSION_DIR, "metadata.yaml"), "w") as f:
        import yaml
        yaml.dump(metadata, f)

    with open(os.path.join(SUBMISSION_DIR, "README.md"), "w") as f:
        f.write("# Azlon GPT4o Submission\n")
        f.write("This submission was generated by an autonomous coding workflow.\n")

    print("All tasks done. Results stored at:", SUBMISSION_DIR)
    print("You can now run:\n  python -m analysis.get_results evaluation/lite/20250108_Azlon_gpt4o\n")

if __name__ == "__main__":
    asyncio.run(main())
