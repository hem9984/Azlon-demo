import os
import time
import json
import jsonlines
import asyncio
import pathlib

from restack_ai import Restack
from restack_ai.restack import CloudConnectionOptions

# 1) Path inside the container where your fork is mounted
SWE_BENCH_BASE = "/app/swe_bench_fork"

# 2) Location of the SWE-bench tasks you want to run (lite or test)
#    For example, let's assume 'lite' tasks:
TASKS_FILE = os.path.join(SWE_BENCH_BASE, "dataset/lite/tasks.jsonl")

# 3) Your submission folder, e.g. "evaluation/lite/20241228_mytool_gpt4"
SPLIT = "lite"
DATE_MODEL = "20241228_Azlon-demo_gpt4o"
SUBMISSION_DIR = os.path.join(SWE_BENCH_BASE, "evaluation", SPLIT, DATE_MODEL)
LOGS_DIR = os.path.join(SUBMISSION_DIR, "logs")
TRAJS_DIR = os.path.join(SUBMISSION_DIR, "trajs")
ALL_PREDS_FILE = os.path.join(SUBMISSION_DIR, "all_preds.jsonl")

# Ensure directories exist
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TRAJS_DIR, exist_ok=True)

def convert_task_to_prompts(task: dict):
    """
    Convert the SWE-bench task into the prompt format your tool expects.
    You can customize how 'task_description' and 'input' map to 'user_prompt' + 'test_conditions'.
    """
    task_id = task["task_id"]
    desc = task.get("task_description", "")
    buggy_code = task.get("input", "")

    user_prompt = f"Task ID: {task_id}\n\n{desc}"
    test_conditions = buggy_code

    return user_prompt, test_conditions

async def run_swe_bench():
    # 1) Setup the Restack client
    connection_options = CloudConnectionOptions(
        engine_id="local",
        api_key=None,
        address=os.getenv("RESTACK_TEMPORAL_ADDRESS", "localhost:7233"),
        api_address=os.getenv("RESTACK_ENGINE_ADDRESS", "localhost:6233"),
        temporal_namespace="default"
    )
    client = Restack(connection_options)

    # 2) Collect final predictions here
    all_preds = []

    # 3) Read tasks one by one
    if not os.path.isfile(TASKS_FILE):
        print(f"ERROR: {TASKS_FILE} does not exist.")
        return

    with jsonlines.open(TASKS_FILE, mode="r") as reader:
        for task in reader:
            task_id = task["task_id"]
            user_prompt, test_conditions = convert_task_to_prompts(task)

            # Create unique workflow ID
            workflow_id = f"{task_id}-{int(time.time()*1000)}"

            try:
                # 4) Run your workflow
                run_id = await client.schedule_workflow(
                    workflow_name="AutonomousCodingWorkflow",
                    workflow_id=workflow_id,
                    input={"user_prompt": user_prompt, "test_conditions": test_conditions}
                )
                result = await client.get_workflow_result(workflow_id=workflow_id, run_id=run_id)

                # For demonstration, let's assume your final patch is in result["patch"]
                # If it's only True/False, you'd adapt accordingly.
                final_patch = result.get("patch", "Placeholder final patch")

                # Write logs/patches/etc to logs/<task_id>/
                task_logs_dir = os.path.join(LOGS_DIR, task_id)
                os.makedirs(task_logs_dir, exist_ok=True)

                # patch.diff
                patch_path = os.path.join(task_logs_dir, "patch.diff")
                with open(patch_path, "w") as f:
                    f.write(final_patch)

                # report.json
                with open(os.path.join(task_logs_dir, "report.json"), "w") as f:
                    f.write(json.dumps({
                        "task_id": task_id,
                        "success": bool(result),
                        "timestamp": int(time.time())
                    }, indent=2))

                # run_instance.log
                run_log_path = os.path.join(task_logs_dir, "run_instance.log")
                with open(run_log_path, "w") as f:
                    f.write("Placeholder log of the workflow steps...")

                # test_output.txt
                test_out_path = os.path.join(task_logs_dir, "test_output.txt")
                with open(test_out_path, "w") as f:
                    f.write("Placeholder test output...")

                # reasoning trace (trajs/<task_id>.md)
                reasoning_trace_path = os.path.join(TRAJS_DIR, f"{task_id}.md")
                with open(reasoning_trace_path, "w") as f:
                    f.write(f"# Reasoning trace for {task_id}\n")
                    f.write("Detailed chain of thought or step-by-step logs...")

                # Store final patch in all_preds.jsonl
                all_preds.append({"task_id": task_id, "output": final_patch})

            except Exception as e:
                print(f"Error running task {task_id}: {e}")

    # 5) Write all_preds.jsonl
    with jsonlines.open(ALL_PREDS_FILE, mode="w") as writer:
        writer.write_all(all_preds)

    print(f"Done! Wrote submission artifacts to {SUBMISSION_DIR}")

if __name__ == "__main__":
    asyncio.run(run_swe_bench())
