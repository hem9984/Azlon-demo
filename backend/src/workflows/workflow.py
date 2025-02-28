# ./backend/src/workflows/workflow.py
from restack_ai.workflow import workflow, import_functions, log  # type: ignore
from dataclasses import dataclass
from datetime import timedelta
import os
import shutil
import time

with import_functions():
    from src.functions.functions import (
        generate_code, run_locally, validate_output, pre_flight_run,
        GenerateCodeInput, GenerateCodeOutput, RunCodeInput, RunCodeOutput,  # type: ignore
        ValidateCodeInput, ValidateCodeOutput, PreFlightOutput  # type: ignore
    )
    from src.utils.file_handling import (
        PreFlightManager, GitManager, CodeInclusionManager
    )

@dataclass
class WorkflowInputParams:
    user_prompt: str
    test_conditions: str

@workflow.defn()
class AutonomousCodingWorkflow:
    @workflow.run
    async def run(self, input: WorkflowInputParams):
        """
        Steps:
         1) Create a fresh ephemeral workspace.
         2) Possibly run pre_flight_run if files exist in /input.
            - If a Dockerfile is found, build & run once.
            - If no Dockerfile, skip building.
         3) Then do iterative:
            validate_output -> generate_code -> run_locally
            until success or 20 iterations.
         4) Copy final code to final_<timestamp>.
        """
        log.info("AutonomousCodingWorkflow started", input=input)
        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")

        # Make ephemeral workspace
        stamp = time.strftime("%Y%m%d_%H%M%S")
        workspace_path = os.path.join(base_output, f"workspace_{stamp}")
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
        os.makedirs(workspace_path, exist_ok=True)

        pfm = PreFlightManager()
        preflight_result = None
        run_result = ""

        if pfm.has_input_files():
            log.info("Pre-flight: merging user code + building container IF Dockerfile is found.")
            preflight_result = await workflow.step(
                pre_flight_run, #type: ignore
                start_to_close_timeout=timedelta(seconds=600)
            )
            self._copy_preflight_workspace(preflight_result, workspace_path)

            # runOutput is from PreFlightOutput (docker logs or skip message)
            run_result = preflight_result.runOutput
            log.info("Pre-flight done. Output:\n" + run_result)
        else:
            log.info("No files in /input folder, skipping preflight.")

        iteration = 0
        max_iterations = 20

        while iteration < max_iterations:
            iteration += 1
            log.info(f"[Iteration {iteration}] Validate code, then (if needed) generate & run code.")

            # Gather the ephemeral workspace state
            cm = CodeInclusionManager(workspace_path)
            code_context = cm.build_code_context(
                user_prompt=input.user_prompt,
                test_conditions=input.test_conditions,
                previous_output=run_result
            )

            # The code_context uses 'dirTree', 'dockerfile', 'files'
            val_input = ValidateCodeInput(
                dirTree=code_context["dirTree"] or "No directory tree.",
                dockerfile=code_context["dockerfile"] or "No Dockerfile yet",
                files=code_context["files"],
                output=run_result,
                userPrompt=input.user_prompt,
                testConditions=input.test_conditions,
                iteration=iteration
            )
            val_output: ValidateCodeOutput = await workflow.step(
                validate_output, #type: ignore
                val_input,
                start_to_close_timeout=timedelta(seconds=300)
            )

            if val_output.result:
                log.info("Validation succeeded. Workflow completed successfully.")
                self._copy_final_workspace(workspace_path, base_output)
                return True
            else:
                log.warning(f"Validation failed. Reason: {val_output.reason}")
                log.warning(f"Suspected files: {[sf.filename for sf in val_output.suspectedFiles]}")

                # Include full content for next iteration
                self._inject_full_content_for_suspected(workspace_path, val_output)

                # Generate new code
                gen_output: GenerateCodeOutput = await workflow.step(
                    generate_code, #type: ignore
                    GenerateCodeInput(
                        userPrompt=input.user_prompt,
                        testConditions=input.test_conditions,
                        dirTree=code_context["dirTree"],
                        preflightResult=preflight_result,
                        validationResult=val_output
                    ),
                    start_to_close_timeout=timedelta(seconds=300)
                )

                # Merge changes
                gm = GitManager(workspace_path)
                gm.merge_llm_changes(
                    llm_dockerfile=gen_output.dockerfile,
                    llm_files=gen_output.files
                )

                # Run container
                run_result_obj = await workflow.step(
                    run_locally, #type: ignore
                    RunCodeInput(repo_path=workspace_path),
                    start_to_close_timeout=timedelta(seconds=900)
                )
                run_result = run_result_obj.output

        log.warning("Max iterations (20) reached without success.")
        self._copy_final_workspace(workspace_path, base_output)
        return False

    def _inject_full_content_for_suspected(self, repo_path: str, val_output: ValidateCodeOutput):
        """
        Attach a new attribute 'fullContent' to each suspectedFile with its complete text.
        This isn't in the BAML schema, but helps the LLM see the entire content in generate_code.
        """
        for sf in val_output.suspectedFiles:
            file_path = os.path.join(repo_path, sf.filename)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    setattr(sf, "fullContent", content)
                except Exception as e:
                    log.error(f"Could not read {sf.filename}: {e}")
                    setattr(sf, "fullContent", f"ERROR reading: {e}")
            else:
                setattr(sf, "fullContent", f"File {sf.filename} not found.")

    def _copy_preflight_workspace(self, pre_flight_result: PreFlightOutput, workspace_path: str):
        """
        The preflight code is put into a folder named 'preflight_<timestamp>'.
        We copy it into the main ephemeral workspace for the iteration cycle.
        """
        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
        preflight_folders = [
            d for d in os.listdir(base_output) if d.startswith("preflight_")
        ]
        if not preflight_folders:
            return
        preflight_folders.sort()
        latest_preflight = preflight_folders[-1]
        src_folder = os.path.join(base_output, latest_preflight)

        if os.path.exists(src_folder):
            for item in os.listdir(src_folder):
                s = os.path.join(src_folder, item)
                d = os.path.join(workspace_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

    def _copy_final_workspace(self, workspace_path: str, base_output: str):
        """
        Copy ephemeral workspace to final_<timestamp> so the user can inspect all results.
        """
        final_stamp = time.strftime("%Y%m%d_%H%M%S")
        final_dir = os.path.join(base_output, f"final_{final_stamp}")
        if os.path.exists(final_dir):
            shutil.rmtree(final_dir)
        shutil.copytree(workspace_path, final_dir)
        log.info(f"Final workspace copied to {final_dir}")
