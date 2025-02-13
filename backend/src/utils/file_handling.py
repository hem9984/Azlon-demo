# ./backend/src/utils/file_handling.py
import os
import re
import json
import csv
import subprocess
import time
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

from src.baml_client.types import PreFlightOutput

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
        subprocess.run(["git", "config", "user.email", "azlon@local"], cwd=self.repo_path, check=True)

    def _commit_all(self, message: str, allow_empty: bool=True):
        subprocess.run(["git", "add", "-A"], cwd=self.repo_path, check=True)
        cmd = ["git", "commit", "-m", message]
        if allow_empty:
            cmd.append("--allow-empty")
        subprocess.run(cmd, cwd=self.repo_path, check=True)

    def _auto_merge_theirs(self):
        subprocess.run(
            ["git", "merge", "llm-changes", "-X", "theirs", "--allow-unrelated-histories"],
            cwd=self.repo_path,
            check=True
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

    def build_code_context(self, user_prompt: str, test_conditions: str, previous_output: str) -> Dict[str, Any]:
        tree_str = self._build_directory_tree()
        dockerfile_content = self._read_dockerfile()
        code_files = self._gather_files()
        return {
            "dirTree": tree_str,
            "dockerfile": dockerfile_content,
            "files": code_files
        }

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
                    return json.dumps({
                        "column_names": [],
                        "sample_rows": [],
                        "summary": "CSV has no header row or is empty."
                    }, indent=2)

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
                    "summary": summary_text
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
                pat_def = re.compile(r'^\s*(def|class)\s+\w+.*:')
                pat_return = re.compile(r'\breturn\b')
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
    def has_input_files(self) -> bool:
        input_dir = os.path.join(os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input")
        if not os.path.isdir(input_dir):
            return False
        for _, dirs, files in os.walk(input_dir):
            if files:
                return True
        return False

    def perform_preflight_merge_and_run(self) -> "PreFlightOutput":
        """
        Create ephemeral folder, merges user code from /input.
        If there's a Dockerfile, build & run once. Otherwise skip building.
        Returns PreFlightOutput with dirTree & runOutput describing success/failure.
        """
        base_output = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run_folder = os.path.join(base_output, f"preflight_{stamp}")
        if os.path.exists(run_folder):
            shutil.rmtree(run_folder)
        os.makedirs(run_folder, exist_ok=True)

        user_json = self._collect_input_files()
        from src.baml_client.types import PreFlightOutput
        from .file_handling import GitManager, run_tree_command

        gm = GitManager(run_folder)
        gm.merge_llm_changes(
            llm_dockerfile=user_json["dockerfile"].strip() or None,
            llm_files=user_json["files"]
        )

        tree_str = run_tree_command(run_folder)

        # If no Dockerfile, skip building
        if not user_json["dockerfile"].strip():
            return PreFlightOutput(
                dirTree=tree_str,
                runOutput="No Dockerfile found. Preflight was skipped."
            )

        # Attempt Docker build & run
        try:
            build_cmd = ["docker", "build", "-t", "preflight_app", run_folder]
            build_proc = subprocess.run(build_cmd, capture_output=True, text=True)

            if build_proc.returncode != 0:
                return PreFlightOutput(
                    dirTree=tree_str,
                    runOutput=(build_proc.stderr or build_proc.stdout)
                )

            run_cmd = [
                "docker", "run", "--rm",
                "-v", f"{run_folder}:/app",
                "preflight_app"
            ]
            run_proc = subprocess.run(run_cmd, capture_output=True, text=True)
            return PreFlightOutput(
                dirTree=run_tree_command(run_folder),
                runOutput=(run_proc.stderr or run_proc.stdout)
                if run_proc.returncode != 0 else run_proc.stdout
            )
        except Exception as e:
            return PreFlightOutput(
                dirTree=tree_str,
                runOutput=f"Preflight exception: {e}"
            )

    def _collect_input_files(self) -> Dict[str, Any]:
        """
        Gather all subdirs/files from /input (except .git). The first Dockerfile becomes user_json["dockerfile"].
        Everything else goes into user_json["files"].
        """
        input_dir = os.path.join(os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input")
        dockerfile_contents = ""
        collected = []

        if not os.path.isdir(input_dir):
            return {"dockerfile": "", "files": []}

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

        return {
            "dockerfile": dockerfile_contents,
            "files": collected
        }
