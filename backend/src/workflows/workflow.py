# Copyright (C) 2024 Harrison E. Muchnic
# This program is licensed under the Affero General Public License (AGPL).
# See the LICENSE file for details.

# ./backend/src/workflows/workflow.py

from restack_ai.workflow import workflow, import_functions, log
from dataclasses import dataclass
from datetime import timedelta

with import_functions():
    from src.functions.functions import (
        generate_code,
        run_locally,
        validate_output,
        create_diff,
        GenerateCodeInput,
        RunCodeInput,
        ValidateOutputInput
    )

@dataclass
class WorkflowInputParams:
    user_prompt: str
    test_conditions: str

@workflow.defn()
class AutonomousCodingWorkflow:
    @workflow.run
    async def run(self, input: WorkflowInputParams):
        log.info("AutonomousCodingWorkflow started", input=input)

        # Step 1: Generate initial code
        gen_output = await workflow.step(
            generate_code,
            GenerateCodeInput(
                user_prompt=input.user_prompt,
                test_conditions=input.test_conditions
            ),
            start_to_close_timeout=timedelta(seconds=300)
        )
        dockerfile = gen_output.dockerfile
        files = gen_output.files

        prev_files = files[:]  # Keep a copy for patch diffs

        iteration_count = 0
        max_iterations = 20

        # We'll store a history of steps for the reasoning trace
        steps = []

        while iteration_count < max_iterations:
            iteration_count += 1
            step_info = {
                "iteration": iteration_count,
                "files_before": [f.copy() for f in files],
                "dockerfile_before": dockerfile
            }

            run_output = await workflow.step(
                run_locally,
                RunCodeInput(dockerfile=dockerfile, files=files),
                start_to_close_timeout=timedelta(seconds=300)
            )
            step_info["run_output"] = run_output.output

            val_output = await workflow.step(
                validate_output,
                ValidateOutputInput(
                    dockerfile=dockerfile,
                    files=files,
                    output=run_output.output,
                    test_conditions=input.test_conditions
                ),
                start_to_close_timeout=timedelta(seconds=300)
            )

            step_info["validate_result"] = val_output.result
            step_info["files_after"] = val_output.files if val_output.files else []
            steps.append(step_info)

            # Compute patch from prev_files -> new files
            patch_str = create_diff(prev_files, val_output.files or [])
            prev_files = val_output.files or prev_files

            if val_output.result:
                log.info("AutonomousCodingWorkflow completed successfully")
                # Return the final patch and entire step history
                return {
                    "success": True,
                    "patch": patch_str,
                    "steps": steps
                }
            else:
                # If not done, update dockerfile & files in-memory
                if val_output.dockerfile:
                    dockerfile = val_output.dockerfile
                changed_files = val_output.files or []
                for changed_file in changed_files:
                    found = False
                    for i, existing_file in enumerate(files):
                        if existing_file["filename"] == changed_file["filename"]:
                            files[i]["content"] = changed_file["content"]
                            found = True
                            break
                    if not found:
                        files.append(changed_file)

        log.warn("AutonomousCodingWorkflow reached max iterations without success")
        return {
            "success": False,
            "patch": "",
            "steps": steps
        }
