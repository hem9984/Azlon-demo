# ./backend/src/workflows/workflow.py
import os
import shutil
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from restack_ai.workflow import import_functions, log, workflow  # type: ignore

with import_functions():
    from src.functions.functions import PreFlightOutput  # type: ignore
    from src.functions.functions import RunCodeOutput  # type: ignore
    from src.functions.functions import (
        GenerateCodeInput,
        GenerateCodeOutput,
        RunCodeInput,
        ValidateCodeInput,
        ValidateCodeOutput,
        generate_code,
        pre_flight_run,
        run_with_e2b,
        validate_output,
    )
    from src.utils.file_handling import CodeInclusionManager, GitManager, PreFlightManager


@dataclass
class WorkflowInputParams:
    user_prompt: str
    test_conditions: str
    user_id: Optional[str] = None


@workflow.defn()
class AutonomousCodingWorkflow:
    @workflow.run
    async def run(self, input: WorkflowInputParams):
        # need to follow new flow instructions that rely on APIs
        """
        Steps:
         1) Create MinIO bucket/directory for user_id/run_id
         2) Possibly run pre_flight_run if files exist in /input or MinIO.
            - If a Dockerfile is found, build & run once using E2B.
            - If no Dockerfile, skip building.
         3) Then do iterative:
            validate_output -> generate_code -> run_with_e2b
            until success or 20 iterations.
         4) Final code is already stored in MinIO under user_id/run_id
        """
        log.info("AutonomousCodingWorkflow started", input=input)

        # Extract user_id and generate run_id based on timestamp
        user_id = input.user_id or "anonymous"
        run_id = f"{int(time.time() * 1000)}"

        log.info(f"Running workflow for user_id={user_id}, run_id={run_id}")

        # Create bucket for file storage in MinIO
        # This is done automatically by the file upload functions

        # Initialize MinIO directory structure for this run
        from src.file_server import create_bucket_if_not_exists

        bucket_name = "azlon-files"
        create_bucket_if_not_exists(bucket_name)

        # For backward compatibility, we still need to create local directories
        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")

        # Create user directory if it doesn't exist
        user_dir = os.path.join(base_output, user_id)
        os.makedirs(user_dir, exist_ok=True)

        # Create run directory
        run_dir = os.path.join(user_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # Make ephemeral workspace inside the run directory
        workspace_path = os.path.join(run_dir, "workspace")
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
        os.makedirs(workspace_path, exist_ok=True)

        pfm = PreFlightManager(user_id=user_id, run_id=run_id)
        preflight_result = None
        run_result = ""

        if pfm.has_input_files():
            log.info("Pre-flight: merging user code + building container IF Dockerfile is found.")
            # Create a task_queue_context dictionary with user_id and run_id
            context = {"user_id": user_id, "run_id": run_id}
            preflight_result = await workflow.step(
                pre_flight_run,  # type: ignore
                task_queue_context=context,
                start_to_close_timeout=timedelta(seconds=600),
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
            log.info(
                f"[Iteration {iteration}] Validate code, then (if needed) generate & run code."
            )

            # For code context, gather files from either local workspace (for compatibility)
            # or from MinIO storage
            cm = CodeInclusionManager(workspace_path)
            code_context = cm.build_code_context(
                user_prompt=input.user_prompt,
                test_conditions=input.test_conditions,
                previous_output=run_result,
            )

            # The code_context uses 'dirTree', 'dockerfile', 'files'
            # Create ValidateCodeInput and add user_id and run_id as attributes
            val_input = ValidateCodeInput(
                dirTree=code_context["dirTree"] or "No directory tree.",
                dockerfile=code_context["dockerfile"] or "No Dockerfile yet",
                files=code_context["files"],
                output=run_result,
                userPrompt=input.user_prompt,
                testConditions=input.test_conditions,
                iteration=iteration,
            )
            # Create a task_queue_context dictionary with user_id and run_id
            context = {"user_id": user_id, "run_id": run_id}
            val_output: ValidateCodeOutput = await workflow.step(
                validate_output,  # type: ignore
                val_input,
                task_queue_context=context,
                start_to_close_timeout=timedelta(seconds=300),
            )

            if val_output.result:
                log.info(
                    f"Validation succeeded for user {user_id}, run {run_id}. Workflow completed successfully."
                )
                # No need to copy to a final workspace as we're using MinIO storage
                return True
            else:
                log.warning(f"Validation failed. Reason: {val_output.reason}")
                log.warning(f"Suspected files: {[sf.filename for sf in val_output.suspectedFiles]}")

                # Include full content for next iteration
                self._inject_full_content_for_suspected(workspace_path, val_output)

                # Generate new code
                # Create GenerateCodeInput and add user_id and run_id as attributes
                gen_input = GenerateCodeInput(
                    userPrompt=input.user_prompt,
                    testConditions=input.test_conditions,
                    dirTree=code_context["dirTree"],
                    preflightResult=preflight_result,
                    validationResult=val_output,
                )
                # Create a task_queue_context dictionary with user_id and run_id
                context = {"user_id": user_id, "run_id": run_id}
                gen_output: GenerateCodeOutput = await workflow.step(
                    generate_code,  # type: ignore
                    gen_input,
                    task_queue_context=context,
                    start_to_close_timeout=timedelta(seconds=300),
                )

                # Merge changes locally (for compatibility) and also to MinIO
                gm = GitManager(workspace_path)
                gm.merge_llm_changes(
                    llm_dockerfile=gen_output.dockerfile, llm_files=gen_output.files
                )

                # Also upload changes to MinIO
                self._upload_changes_to_minio(user_id, run_id, gen_output)

                # Run container using E2B, which will pull files from MinIO
                run_input = RunCodeInput(repo_path=workspace_path, user_id=user_id, run_id=run_id)

                # Create a task_queue_context dictionary with user_id and run_id
                context = {"user_id": user_id, "run_id": run_id}
                run_result_obj = await workflow.step(
                    run_with_e2b,  # type: ignore
                    run_input,
                    task_queue_context=context,
                    start_to_close_timeout=timedelta(seconds=900),
                )
                run_result = run_result_obj.output

        log.warning(
            f"Max iterations (20) reached without success for user {user_id}, run {run_id}."
        )
        # No need to copy to a final workspace as everything is in MinIO
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
        Copy preflight files into the main workspace.
        With the new directory structure, the preflight files are stored in the same
        run directory under a 'preflight' subdirectory.
        """
        # Extract the run directory from the workspace path (parent of workspace)
        run_dir = os.path.dirname(workspace_path)
        preflight_dir = os.path.join(run_dir, "preflight")

        if os.path.exists(preflight_dir):
            for item in os.listdir(preflight_dir):
                s = os.path.join(preflight_dir, item)
                d = os.path.join(workspace_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

    def _upload_changes_to_minio(self, user_id: str, run_id: str, gen_output: GenerateCodeOutput):
        """
        Upload generated code changes to MinIO.
        This ensures the files are available for E2B execution.
        """
        import io

        from src.file_server import create_bucket_if_not_exists, upload_file

        # The bucket name for storing files
        bucket_name = "azlon-files"

        # Ensure bucket exists
        create_bucket_if_not_exists(bucket_name)

        # Upload Dockerfile if present
        if gen_output.dockerfile and gen_output.dockerfile.strip():
            object_name = f"{user_id}/{run_id}/Dockerfile"
            upload_file(io.BytesIO(gen_output.dockerfile.encode("utf-8")), bucket_name, object_name)
            log.info(f"Uploaded Dockerfile to MinIO: {object_name}")

        # Upload other files
        if gen_output.files:
            for file_item in gen_output.files:
                object_name = f"{user_id}/{run_id}/{file_item.filename}"
                upload_file(io.BytesIO(file_item.content.encode("utf-8")), bucket_name, object_name)
                log.info(f"Uploaded file to MinIO: {object_name}")
