#./backend/src/workflows/workflow.py
from restack_ai.workflow import workflow, import_functions, log
from dataclasses import dataclass
from datetime import timedelta
import os

with import_functions():
    from src.functions.functions import (
        generate_code, run_locally, validate_output, pre_flight_run,
        GenerateCodeInput, RunCodeInput, ValidateOutputInput, PreFlightOutput
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

        # 0) OPTIONAL PRE-FLIGHT STEP
        input_dir = os.path.join(os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input")
        has_user_files = False
        if os.path.isdir(input_dir):
            for root, dirs, files in os.walk(input_dir):
                if files:
                    has_user_files = True
                    break

        pre_flight_result = None
        if has_user_files:
            log.info("Pre-flight: found user-provided code. Let's build/run it to see what happens.")
            pre_flight_result: PreFlightOutput = await workflow.step(
                pre_flight_run,
                start_to_close_timeout=timedelta(seconds=300)
            )
            log.info("Pre-flight completed. Output:\n" + pre_flight_result.run_output)

        # 1) Generate code (first iteration)
        pre_flight_output_text = ""
        if pre_flight_result:
            pre_flight_output_text = (
                f"\n\nWe ran the user-provided code. The container output was:\n\n"
                f"{pre_flight_result.run_output}\n\n"
                f"The code structure is:\n{pre_flight_result.dir_tree}\n\n"
                "Please modify or create a Dockerfile if needed, and adjust the code to meet new test conditions.\n"
            )

        gen_output = await workflow.step(
            generate_code,
            GenerateCodeInput(
                user_prompt=input.user_prompt + pre_flight_output_text,
                test_conditions=input.test_conditions
            ),
            start_to_close_timeout=timedelta(seconds=300)
        )

        dockerfile = gen_output.dockerfile
        files = gen_output.files  # list of {"filename":..., "content":...}

        iteration_count = 0
        max_iterations = 20

        while iteration_count < max_iterations:
            iteration_count += 1
            log.info(f"Iteration {iteration_count} start")

            run_output = await workflow.step(
                run_locally,
                RunCodeInput(dockerfile=dockerfile, files=files),
                start_to_close_timeout=timedelta(seconds=300)
            )

            val_output = await workflow.step(
                validate_output,
                ValidateOutputInput(
                    dockerfile=dockerfile,
                    files=files,
                    output=run_output.output,
                    test_conditions=input.test_conditions,
                    iteration=iteration_count
                ),
                start_to_close_timeout=timedelta(seconds=300)
            )

            if val_output.result:
                log.info("AutonomousCodingWorkflow completed successfully")
                return True
            else:
                changed_files = val_output.files if val_output.files else []
                if val_output.dockerfile:
                    dockerfile = val_output.dockerfile

                # Merge changes
                for changed_file in changed_files:
                    changed_filename = changed_file["filename"]
                    changed_content = changed_file["content"]
                    found = False
                    for i, existing_file in enumerate(files):
                        if existing_file["filename"] == changed_filename:
                            files[i]["content"] = changed_content
                            found = True
                            break
                    if not found:
                        files.append({"filename": changed_filename, "content": changed_content})

        log.warn("AutonomousCodingWorkflow reached max iterations without success")
        return False
