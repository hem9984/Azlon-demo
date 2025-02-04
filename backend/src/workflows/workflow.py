#./backend/src/workflows/workflow.py
from restack_ai.workflow import workflow, import_functions, log
from dataclasses import dataclass
from datetime import timedelta
import os
import shutil
import time

with import_functions():
    from src.functions.functions import (
        generate_code, run_locally, validate_output, pre_flight_run,
        GenerateCodeInput, GenerateCodeOutput, RunCodeInput, RunCodeOutput,
        ValidateCodeInput, ValidateCodeOutput, PreFlightOutput
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
        1) Fresh ephemeral workspace each run
        2) Possibly do pre_flight_run
        3) generate_code => merges files
        4) repeated run_locally + validate_output
        5) copy final to 'final_YYYYMMDD_HHMMSS'
        """
        log.info("AutonomousCodingWorkflow started", input=input)

        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")

        # Make a brand new ephemeral workspace
        stamp = time.strftime("%Y%m%d_%H%M%S")
        workspace_path = os.path.join(base_output, f"workspace_{stamp}")
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
        os.makedirs(workspace_path, exist_ok=True)

        # Maybe do pre_flight if user has code in /input
        pfm = PreFlightManager()
        pre_flight_result = None
        if pfm.has_input_files():
            log.info("Pre-flight: merging user-provided code & running once.")
            pre_flight_result = await workflow.step(
                pre_flight_run,
                start_to_close_timeout=timedelta(seconds=600)
            )
            log.info("Pre-flight done. Output:\n" + pre_flight_result.run_output)

        # Step: generate_code
        gen_output: GenerateCodeOutput = await workflow.step(
            generate_code,
            GenerateCodeInput(
                userPrompt=input.user_prompt,
                testConditions=input.test_conditions,
                preflight_result=pre_flight_result
            ),
            start_to_close_timeout=timedelta(seconds=300)
        )

        # Merge initial code
        gm = GitManager(workspace_path)
        gm.merge_llm_changes(
            llm_dockerfile=gen_output.dockerfile,
            llm_files=gen_output.files
        )

        iteration = 0
        max_iterations = 20
        previous_output = ""

        while iteration < max_iterations:
            iteration += 1
            log.info(f"Iteration {iteration} start")

            # run_locally => Docker build & run in ephemeral workspace
            run_result: RunCodeOutput = await workflow.step(
                run_locally,
                RunCodeInput(repo_path=workspace_path),
                start_to_close_timeout=timedelta(seconds=900)
            )
            previous_output = run_result.output

            # Build code context to pass to LLM
            cm = CodeInclusionManager(workspace_path)
            code_context = cm.build_code_context(
                user_prompt=input.user_prompt,
                test_conditions=input.test_conditions,
                previous_output=previous_output
            )

            val_input = ValidateCodeInput(
                dockerfile=code_context["dockerfile"],
                files=code_context["files"],
                output=previous_output,
                userPrompt=input.user_prompt,
                testConditions=input.test_conditions,
                iteration=iteration,
                dirTree=code_context["dir_tree"]  # show subfolders
            )

            val_output: ValidateCodeOutput = await workflow.step(
                validate_output,
                val_input,
                start_to_close_timeout=timedelta(seconds=300)
            )

            if val_output.result:
                log.info("Workflow completed successfully.")
                self._copy_final_workspace(workspace_path, base_output)
                return True
            else:
                gm.merge_llm_changes(
                    llm_dockerfile=val_output.dockerfile,
                    llm_files=val_output.files
                )

        log.warning("Max iterations hit, no success.")
        self._copy_final_workspace(workspace_path, base_output)
        return False

    def _copy_final_workspace(self, workspace_path: str, base_output: str):
        """
        Copies ephemeral workspace to final_<timestamp> so user can see all subfolders,
        including any new CSVs or files created by Docker container.
        """
        final_stamp = time.strftime("%Y%m%d_%H%M%S")
        final_dir = os.path.join(base_output, f"final_{final_stamp}")
        if os.path.exists(final_dir):
            shutil.rmtree(final_dir)
        shutil.copytree(workspace_path, final_dir)
        log.info(f"Final workspace copied to {final_dir}")
