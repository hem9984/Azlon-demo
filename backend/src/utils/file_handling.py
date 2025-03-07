# ./backend/src/utils/file_handling.py
import csv
import json
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Union

# Import E2B for sandbox execution
try:
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False

logger = logging.getLogger(__name__)

# Re-export file_server functions
from src.file_server import (
    create_bucket_if_not_exists,
    download_file,
    generate_directory_tree,
    list_files,
    upload_file,
)


# Define PreFlightOutput locally to avoid BAML dependency issues
class PreFlightOutput:
    def __init__(
        self,
        result: bool = False,
        errors: Optional[List[str]] = None,
        dirTree: str = "",
        runOutput: str = "",
    ):
        self.result = result
        self.errors = errors or []
        self.dirTree = dirTree
        self.runOutput = runOutput


# ---------------------------------------------------------------------
# GitManager
# ---------------------------------------------------------------------


class GitManager:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        if not os.path.isdir(repo_path):
            os.makedirs(repo_path, exist_ok=True)
        self._ensure_git_repo()

    def _ensure_git_repo(self):
        git_dir = os.path.join(self.repo_path, ".git")
        if not os.path.isdir(git_dir):
            subprocess.run(["git", "init", "--initial-branch=main"], cwd=self.repo_path, check=True)
            self._config_identity()
            self._commit_all("Initial empty commit", allow_empty=True)

    def _config_identity(self):
        subprocess.run(["git", "config", "user.name", "AzlonBot"], cwd=self.repo_path, check=True)
        subprocess.run(
            ["git", "config", "user.email", "azlon@local"], cwd=self.repo_path, check=True
        )

    def _commit_all(self, message: str, allow_empty: bool = True):
        subprocess.run(["git", "add", "-A"], cwd=self.repo_path, check=True)
        cmd = ["git", "commit", "-m", message]
        if allow_empty:
            cmd.append("--allow-empty")
        subprocess.run(cmd, cwd=self.repo_path, check=True)

    def _auto_merge_theirs(self):
        subprocess.run(
            ["git", "merge", "llm-changes", "-X", "theirs", "--allow-unrelated-histories"],
            cwd=self.repo_path,
            check=True,
        )

    def merge_llm_changes(self, llm_dockerfile: Optional[str], llm_files: Optional[List[Any]]):
        """
        If llm_dockerfile is provided, we treat it as Dockerfile content.
        If llm_files is a list of {filename, content} or typed FileItem, we write them.
        Then commit on branch 'llm-changes' and merge with 'main'.
        """
        from src.baml_client.types import FileItem

        changes: List[FileItem] = []

        if llm_dockerfile and llm_dockerfile.strip():
            changes.append(FileItem(filename="Dockerfile", content=llm_dockerfile))

        if llm_files:
            for f in llm_files:
                if isinstance(f, dict):
                    changes.append(FileItem(filename=f["filename"], content=f["content"]))
                else:
                    changes.append(f)

        if not changes:
            return

        subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)
        self._commit_all("Base commit", allow_empty=True)

        subprocess.run(["git", "checkout", "-B", "llm-changes"], cwd=self.repo_path, check=True)

        for item in changes:
            path = os.path.join(self.repo_path, item.filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as ff:
                ff.write(item.content)

        self._commit_all("LLM changes", allow_empty=True)

        subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)
        self._auto_merge_theirs()


# ---------------------------------------------------------------------
# CodeInclusionManager
# ---------------------------------------------------------------------


def run_tree_command(directory: str) -> str:
    try:
        result = subprocess.run(["tree", directory], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        logger.warning(f"Failed to run 'tree' on {directory}: {e}")
        return ""


class CodeInclusionManager:
    """
    Decides what files to include in ValidateCodeInput.files.
    We do partial reading/truncation for large files, and special summarization for CSV.
    """

    special_exts = {".csv", ".numpy", ".npy", ".tsv"}

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.token_count = 0

    def build_code_context(
        self, user_prompt: str, test_conditions: str, previous_output: str
    ) -> Dict[str, Any]:
        tree_str = self._build_directory_tree()
        dockerfile_content = self._read_dockerfile()
        code_files = self._gather_files()
        return {"dirTree": tree_str, "dockerfile": dockerfile_content, "files": code_files}

    def _build_directory_tree(self) -> str:
        raw_tree = run_tree_command(self.repo_path)
        if len(raw_tree) > 5000:
            raw_tree = raw_tree[:5000] + "\n... (truncated directory tree)"
        return raw_tree

    def _read_dockerfile(self) -> str:
        path = os.path.join(self.repo_path, "Dockerfile")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as df:
                return df.read()
        return ""

    def _approx_token_count(self, text: str) -> int:
        return len(text.split())

    def _gather_files(self) -> List[Dict[str, str]]:
        """
        Walk ephemeral workspace, reading each file (except .git, license, Dockerfile).
        Possibly truncates large files, or summarizes CSV, returning {filename, content}.
        """
        final_list = []
        for root, dirs, files in os.walk(self.repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            for fname in files:
                fname_lower = fname.lower()
                if fname_lower in ("dockerfile", "license"):
                    continue
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.repo_path)

                content = self._read_file_with_rules(fname_lower, full_path)
                if content is not None:
                    final_list.append({"filename": rel_path, "content": content})
        return final_list

    def _truncate_if_needed(self, text: str, max_len: int = 100) -> str:
        """If text is longer than max_len, cut it and append '... (truncated)'."""
        if len(text) > max_len:
            return text[:max_len] + "... (truncated)"
        return text

    def _summarize_csv(self, full_path: str, max_lines: int = 2) -> str:
        """
        Summarize a CSV by reading its headers, sampling up to 2 rows,
        and truncating any field > 100 chars.
        Returns a JSON string with { column_names, sample_rows, summary }.
        """
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return json.dumps(
                        {
                            "column_names": [],
                            "sample_rows": [],
                            "summary": "CSV has no header row or is empty.",
                        },
                        indent=2,
                    )

                columns = reader.fieldnames
                sample_rows = []
                for i, row in enumerate(reader):
                    if i >= max_lines:
                        break
                    truncated_row = {}
                    for col in columns:
                        val = row[col] if col in row else ""
                        truncated_row[col] = self._truncate_if_needed(val, 100)
                    sample_rows.append(truncated_row)

                summary_text = f"Total columns: {len(columns)}. Sampled up to {max_lines} row(s)."
                data = {
                    "column_names": columns,
                    "sample_rows": sample_rows,
                    "summary": summary_text,
                }
                return json.dumps(data, indent=2)
        except Exception as e:
            return f"Error reading CSV: {e}"

    def _read_file_with_rules(self, fname_lower: str, full_path: str) -> Optional[str]:
        ext = os.path.splitext(fname_lower)[1]

        # Check for CSV => Summarize
        if ext == ".csv":
            summary = self._summarize_csv(full_path)
            self.token_count += self._approx_token_count(summary)
            return summary

        # Otherwise try reading raw text
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        except:
            return None

        # apply standard rules
        if fname_lower in ("main.py", "app.py"):
            # read entire
            self.token_count += self._approx_token_count(raw_text)
            return raw_text

        # *.py with "test" in name => entire
        if ext == ".py" and "test" in fname_lower:
            self.token_count += self._approx_token_count(raw_text)
            return raw_text

        # readme.md => entire or truncated
        if fname_lower == "readme.md":
            if len(raw_text) > 10000:
                snippet = raw_text[:10000] + "\n... (truncated bottom of readme)"
                self.token_count += self._approx_token_count(snippet)
                return snippet
            else:
                self.token_count += self._approx_token_count(raw_text)
                return raw_text

        # other special ext => only first 2 lines
        if ext in self.special_exts:
            # .csv is already handled, but for .npy, .tsv, etc.:
            lines = raw_text.splitlines()
            snippet = "\n".join(lines[:2]) + "\n... (truncated special ext)"
            self.token_count += self._approx_token_count(snippet)
            return snippet

        # .py => entire unless token_count>60000 => then only def/class/return lines
        if ext == ".py":
            if self.token_count < 60000:
                self.token_count += self._approx_token_count(raw_text)
                return raw_text
            else:
                lines = raw_text.splitlines()
                snippet_lines = []
                pat_def = re.compile(r"^\s*(def|class)\s+\w+.*:")
                pat_return = re.compile(r"\breturn\b")
                for ln in lines:
                    if pat_def.search(ln) or pat_return.search(ln):
                        snippet_lines.append(ln)
                snippet = "\n".join(snippet_lines)
                snippet += "\n# (truncated python file due to token limit)"
                self.token_count += self._approx_token_count(snippet)
                return snippet

        # everything else => entire unless token_count>65000 => skip
        if self.token_count < 65000:
            self.token_count += self._approx_token_count(raw_text)
            return raw_text
        else:
            return None


# ---------------------------------------------------------------------
# PreFlightManager
# ---------------------------------------------------------------------


class PreFlightManager:
    def __init__(
        self,
        user_id: Optional[str] = None,
        run_id: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        self.user_id = user_id or "anonymous"
        self.run_id = run_id or str(int(time.time() * 1000))
        self.bucket_name = bucket_name or "azlon-files"

        # Create bucket if it doesn't exist
        create_bucket_if_not_exists(self.bucket_name)

    @property
    def base_prefix(self) -> str:
        """Get the base prefix for S3 objects"""
        return f"{self.user_id}/{self.run_id}/"

    def get_object_key(self, file_path: str) -> str:
        """Get the full S3 object key for a given file path"""
        return f"{self.user_id}/{self.run_id}/{file_path}"

    def has_input_files(self) -> bool:
        """
        Check if there are input files in the /input directory or in MinIO
        """
        # First check local input directory for backward compatibility
        input_dir = os.path.join(os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input")
        local_has_files = False

        if os.path.isdir(input_dir):
            for _, _, files in os.walk(input_dir):
                if files:
                    local_has_files = True
                    break

        # Then check MinIO
        minio_has_files = False
        try:
            files = list_files(self.bucket_name, f"input/{self.user_id}/")
            if files:
                minio_has_files = True
        except Exception as e:
            logger.error(f"Error checking MinIO for input files: {e}")

        return local_has_files or minio_has_files

    def collect_and_upload_files(self, local_dir: str) -> List[Dict[str, Any]]:
        """
        Collect files from a local directory and upload them to MinIO

        Args:
            local_dir: Local directory to collect files from

        Returns:
            List of information about the uploaded files
        """
        uploaded_files = []

        # Walk the directory and collect files
        for root, _, files in os.walk(local_dir):
            for file in files:
                file_path = os.path.join(root, file)

                # Get the relative path for S3 key
                rel_path = os.path.relpath(file_path, local_dir)
                object_key = self.get_object_key(rel_path)

                # Upload the file to MinIO
                if upload_file(file_path, self.bucket_name, object_key):
                    uploaded_files.append(
                        {
                            "local_path": file_path,
                            "key": object_key,
                            "size": os.path.getsize(file_path),
                            "last_modified": time.time(),
                        }
                    )

        return uploaded_files

    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List files in MinIO with the user/run prefix

        Args:
            prefix: Additional prefix to filter by (after user/run)

        Returns:
            List of file information dictionaries
        """
        full_prefix = self.base_prefix
        if prefix:
            full_prefix = f"{full_prefix}{prefix}"

        return list_files(self.bucket_name, full_prefix)

    def download_file(
        self, object_key: str, local_path: Optional[str] = None
    ) -> Union[bytes, bool]:
        """
        Download a file from MinIO

        Args:
            object_key: S3 object key (relative to user/run prefix)
            local_path: Optional file path to save to. If None, returns the content as bytes.

        Returns:
            bytes or bool: File content as bytes if local_path is None, otherwise True if successful
        """
        full_key = (
            self.get_object_key(object_key)
            if not object_key.startswith(self.base_prefix)
            else object_key
        )
        return download_file(self.bucket_name, full_key, local_path)

    def generate_directory_tree(self) -> str:
        """
        Generate a tree-like representation of files in MinIO for the current user/run prefix

        Returns:
            str: Tree-like representation of files
        """
        return generate_directory_tree(self.bucket_name, self.base_prefix)

    def perform_preflight_merge_and_run(self) -> "PreFlightOutput":
        """
        Create ephemeral folder, merges user code from /input.
        If there's a Dockerfile, build & run once using E2B.
        Returns PreFlightOutput with dirTree & runOutput describing success/failure.
        """
        # Create the directory structure: llm-output/<user_id>/<run_id>/preflight
        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")

        # Create user directory if it doesn't exist
        user_dir = os.path.join(base_output, self.user_id)
        os.makedirs(user_dir, exist_ok=True)

        # Create run directory if it doesn't exist
        run_dir = os.path.join(user_dir, self.run_id)
        os.makedirs(run_dir, exist_ok=True)

        # Create preflight directory inside the run directory
        run_folder = os.path.join(run_dir, "preflight")
        if os.path.exists(run_folder):
            shutil.rmtree(run_folder)
        os.makedirs(run_folder, exist_ok=True)

        logger.info(
            f"Created preflight directory at {run_folder} for user {self.user_id}, run {self.run_id}"
        )

        # Collect files from local input and/or MinIO
        user_json = self._collect_input_files(run_folder)

        # Also upload collected files to MinIO for E2B
        self._upload_files_to_minio(user_json)

        # Generate directory tree (using MinIO if possible)
        try:
            from src.file_server import generate_directory_tree

            tree_str = generate_directory_tree(self.bucket_name, f"{self.user_id}/{self.run_id}/")
        except Exception as e:
            logger.error(f"Error generating MinIO directory tree: {e}")
            # Fallback to local tree
            tree_str = run_tree_command(run_folder)

        # If no Dockerfile, skip building
        if not user_json["dockerfile"].strip():
            return PreFlightOutput(
                result=True,
                dirTree=tree_str,
                runOutput="No Dockerfile found. Preflight was skipped.",
            )

        # Run docker container using E2B
        try:
            from src.e2b_functions import E2BRunner

            e2b = E2BRunner()
            result = e2b.run_docker_container(self.user_id, self.run_id, self.bucket_name)

            # Update the tree after execution
            try:
                tree_str = generate_directory_tree(
                    self.bucket_name, f"{self.user_id}/{self.run_id}/"
                )
            except Exception:
                pass

            success = result["status"] == "success"
            return PreFlightOutput(result=success, dirTree=tree_str, runOutput=result["output"])
        except Exception as e:
            logger.error(f"Error running preflight with E2B: {str(e)}")
            return PreFlightOutput(
                result=False, dirTree=tree_str, runOutput=f"Preflight exception: {e}"
            )

    def _collect_input_files(self, run_folder: str) -> Dict[str, Any]:
        """
        Gather files from /input directory (locally) and/or from MinIO input/ prefix.
        Returns a dictionary with "dockerfile" and "files" keys.
        """
        dockerfile_contents = ""
        collected = []

        # First collect from local input directory
        input_dir = os.path.join(os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input")

        if os.path.isdir(input_dir):
            for root, dirs, files in os.walk(input_dir):
                if ".git" in dirs:
                    dirs.remove(".git")

                for fname in files:
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, input_dir)

                    try:
                        with open(full_path, "r", encoding="utf-8") as ff:
                            content = ff.read()
                    except:
                        content = ""

                    if fname.lower() == "dockerfile" and not dockerfile_contents:
                        dockerfile_contents = content
                    else:
                        collected.append({"filename": rel_path, "content": content})

        # Then check MinIO for input files
        try:
            from src.file_server import download_file, list_files

            files = list_files(self.bucket_name, f"input/{self.user_id}/")

            for file_info in files:
                key = file_info["key"]

                # Skip already processed files
                rel_path = key.replace(f"input/{self.user_id}/", "")
                if any(item["filename"] == rel_path for item in collected):
                    continue

                content = download_file(self.bucket_name, key)
                if content and isinstance(content, bytes):
                    content_str = content.decode("utf-8", errors="replace")

                    if rel_path.lower() == "dockerfile" and not dockerfile_contents:
                        dockerfile_contents = content_str
                    else:
                        collected.append({"filename": rel_path, "content": content_str})
        except Exception as e:
            logger.error(f"Error collecting files from MinIO: {e}")

        return {"dockerfile": dockerfile_contents, "files": collected}

    def _upload_files_to_minio(self, user_json: Dict[str, Any]) -> None:
        """
        Upload the collected files to MinIO for the E2B execution
        """
        try:
            import io

            from src.file_server import create_bucket_if_not_exists, upload_file

            # Ensure bucket exists
            create_bucket_if_not_exists(self.bucket_name)

            # Upload Dockerfile if present
            if user_json["dockerfile"]:
                object_name = f"{self.user_id}/{self.run_id}/Dockerfile"
                upload_file(
                    io.BytesIO(user_json["dockerfile"].encode("utf-8")),
                    self.bucket_name,
                    object_name,
                )

            # Upload other files
            for file_item in user_json["files"]:
                object_name = f"{self.user_id}/{self.run_id}/{file_item['filename']}"
                upload_file(
                    io.BytesIO(file_item["content"].encode("utf-8")), self.bucket_name, object_name
                )
        except Exception as e:
            logger.error(f"Error uploading files to MinIO: {e}")
