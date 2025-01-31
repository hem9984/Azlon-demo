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
        Iterative workflow:
         1) Possibly do pre_flight_run
         2) Generate code, merge to ephemeral workspace
         3) Repeatedly run_locally + validate_output
         4) Copy final workspace into ./llm-output/final_<timestamp>
        """
        log.info("AutonomousCodingWorkflow started", input=input)

        # We'll store ephemeral code in:
        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
        base_workspace = os.path.join(base_output, "workspace")
        os.makedirs(base_workspace, exist_ok=True)

        # Step 0: Possibly do pre-flight
        pfm = PreFlightManager()
        pre_flight_result = None
        if pfm.has_input_files():
            log.info("Pre-flight: merging user-provided code from input/ & running it once.")
            pre_flight_result = await workflow.step(
                pre_flight_run,
                start_to_close_timeout=timedelta(seconds=600)
            )
            log.info("Pre-flight completed. Output:\n" + pre_flight_result.run_output)

        # Step 1: generate initial code
        gen_output: GenerateCodeOutput = await workflow.step(
            generate_code,
            GenerateCodeInput(
                userPrompt=input.user_prompt,
                testConditions=input.test_conditions,
                preflight_result=pre_flight_result
            ),
            start_to_close_timeout=timedelta(seconds=300)
        )

        # Merge initial LLM code -> ephemeral workspace
        gm = GitManager(base_workspace)
        gm.merge_llm_changes(llm_dockerfile=gen_output.dockerfile, llm_files=gen_output.files)

        iteration = 0
        max_iterations = 20
        previous_output = ""

        while iteration < max_iterations:
            iteration += 1
            log.info(f"Iteration {iteration} start")

            # run_locally => Docker build+run (with volume mount)
            run_result: RunCodeOutput = await workflow.step(
                run_locally,
                RunCodeInput(repo_path=base_workspace),
                start_to_close_timeout=timedelta(seconds=900)
            )
            previous_output = run_result.output

            # build code context for validation
            cm = CodeInclusionManager(base_workspace)
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
                iteration=iteration
            )

            val_output: ValidateCodeOutput = await workflow.step(
                validate_output,
                val_input,
                start_to_close_timeout=timedelta(seconds=300)
            )

            if val_output.result:
                log.info("AutonomousCodingWorkflow completed successfully")
                # After success, copy final code to ./llm-output/final_<timestamp>
                self._copy_final_workspace(base_workspace, base_output)
                return True
            else:
                # Merge new changes
                gm.merge_llm_changes(
                    llm_dockerfile=val_output.dockerfile,
                    llm_files=val_output.files
                )

        log.warning("Reached max iterations without success.")
        self._copy_final_workspace(base_workspace, base_output)
        return False

    def _copy_final_workspace(self, workspace_path: str, base_output: str):
        """
        Copies the ephemeral workspace into /llm-output/final_<timestamp> 
        so the user sees the final file state, including any CSVs or subdirs 
        generated at runtime.
        """
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        final_dir = os.path.join(base_output, f"final_{timestamp_str}")
        if os.path.exists(final_dir):
            shutil.rmtree(final_dir)
        shutil.copytree(workspace_path, final_dir)
        log.info(f"Final code state copied to: {final_dir}")
