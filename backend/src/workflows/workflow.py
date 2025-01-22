# ./backend/src/workflows/workflow.py
from restack_ai.workflow import workflow, import_functions, log
from dataclasses import dataclass
from datetime import timedelta
from datetime import datetime

with import_functions():
    from src.functions.functions import generate_code, run_locally, validate_output
    from src.functions.functions import GenerateCodeInput, RunCodeInput, ValidateOutputInput

@dataclass
class WorkflowInputParams:
    user_prompt: str
    test_conditions: str

@workflow.defn()
class AutonomousCodingWorkflow:
    @workflow.run
    async def run(self, input: WorkflowInputParams):
        log.info("AutonomousCodingWorkflow started", input=input)

        gen_output = await workflow.step(
            generate_code,
            GenerateCodeInput(
                user_prompt=input.user_prompt,
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
                    test_conditions=input.test_conditions
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

                # Update the files list in-memory
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
