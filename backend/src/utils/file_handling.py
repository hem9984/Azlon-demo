#./backend/src/utils/file_handling.py
import os
import re
import json
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging
import shutil

from src.baml_client.types import FileItem, PreFlightOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Git Manager
# ---------------------------------------------------------------------

class GitManager:
    """
    Handles initialization and merges in a Git repo-based workspace.
    """
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        if not os.path.isdir(repo_path):
            os.makedirs(repo_path, exist_ok=True)
        self._ensure_git_repo()

    def _ensure_git_repo(self):
        """
        Initialize a Git repo if not present. 
        Use 'main' as default branch, set user config, do an empty commit.
        """
        if not os.path.isdir(os.path.join(self.repo_path, ".git")):
            subprocess.run(["git", "init", "--initial-branch=main"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "config", "user.name", "AzlonBot"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "azlon@local"], cwd=self.repo_path, check=True)
            self._commit_all("Initial empty commit", allow_empty=True)

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

    def merge_llm_changes(self, llm_dockerfile: Optional[str], llm_files: Optional[List[FileItem]]):
        changes: List[FileItem] = []

        # If dockerfile is a string, wrap it in a FileItem or handle separately:
        if llm_dockerfile is not None:
            changes.append(FileItem(filename="Dockerfile", content=llm_dockerfile))

        if llm_files is not None:
            changes.extend(llm_files)  # these are already FileItem objects

        if not changes:
            return  # nothing to merge

        # 1) commit existing code on 'main'
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)
        self._commit_all("Base commit", allow_empty=True)

        # 2) create/reset llm-changes
        subprocess.run(["git", "checkout", "-B", "llm-changes"], cwd=self.repo_path, check=True)

        # 3) write the LLM changes
        for f in changes:
            full_path = os.path.join(self.repo_path, f.filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as ff:
                ff.write(f.content)

        self._commit_all("LLM changes", allow_empty=True)

        # 4) merge them back into main
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)
        self._auto_merge_theirs()



# ---------------------------------------------------------------------
# Code Inclusion Manager
# ---------------------------------------------------------------------

def run_tree_command(directory: str) -> str:
    try:
        result = subprocess.run(["tree", directory], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        logger.warning(f"Failed to run 'tree' in {directory}: {e}")
        return ""

class CodeInclusionManager:
    """
    Builds the context for each iteration's validate_output step.
    1) Directory tree, truncated at 5000 chars
    2) Dockerfile (full)
    3) All other files based on your custom rules:
       - skip LICENSE
       - special_ext => 2 lines
       - main.py/app.py => entire
       - test .py => entire
       - readme => entire or truncated bottom
       - other .py => entire unless token usage > 60000 => only def/class/return lines
       - other => entire unless total tokens>65000 => skip
    """
    special_exts = {".csv", ".numpy", ".npy", ".tsv"}

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.token_count = 0

    def build_code_context(self, user_prompt: str, test_conditions: str, previous_output: str) -> Dict[str, Any]:
        """
        Returns a dict with:
         {
           "dockerfile": <str>,
           "files": [ {filename, content}, ... ],
           "dir_tree": <truncated tree str>
         }
        Caller will pass userPrompt/testConditions/previous_output to the LLM input structure.
        """
        tree_str = self._build_tree_str()
        dockerfile_content = self._read_dockerfile()
        code_files = self._gather_files()

        return {
            "dockerfile": dockerfile_content,
            "files": code_files,
            "dir_tree": tree_str
        }

    def _build_tree_str(self) -> str:
        raw_tree = run_tree_command(self.repo_path)
        if len(raw_tree) > 5000:
            return raw_tree[:5000] + "\n... (truncated directory tree)"
        return raw_tree

    def _read_dockerfile(self) -> str:
        docker_path = os.path.join(self.repo_path, "Dockerfile")
        if not os.path.isfile(docker_path):
            return ""
        with open(docker_path, "r", encoding="utf-8") as df:
            return df.read()

    def _approx_token_count(self, text: str) -> int:
        return len(text.split())

    def _gather_files(self) -> List[Dict[str, str]]:
        """
        Walk the repo, read each file with rules, skip if logic says skip.
        """
        collected = []
        for root, dirs, files in os.walk(self.repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            for fname in files:
                if fname.lower() == "dockerfile" or fname.lower() == "license":
                    continue
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.repo_path)
                content = self._read_file_with_rules(fname, full_path)
                if content is not None:
                    collected.append({"filename": rel_path, "content": content})
        return collected

    def _read_file_with_rules(self, fname: str, full_path: str) -> Optional[str]:
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        except:
            return None

        fname_lower = fname.lower()
        ext = os.path.splitext(fname)[1].lower()

        # main.py or app.py => entire
        if fname_lower in ("main.py", "app.py"):
            self.token_count += self._approx_token_count(raw_text)
            return raw_text

        # test .py => entire
        if ext == ".py" and "test" in fname_lower:
            self.token_count += self._approx_token_count(raw_text)
            return raw_text

        # readme => entire or truncated bottom if > 10000 chars
        if fname_lower == "readme.md":
            if len(raw_text) > 10000:
                truncated = raw_text[:10000] + "\n... (truncated bottom of readme)"
                self.token_count += self._approx_token_count(truncated)
                return truncated
            else:
                self.token_count += self._approx_token_count(raw_text)
                return raw_text

        # special_ext => first 2 lines
        if ext in self.special_exts:
            lines = raw_text.splitlines()
            snippet = "\n".join(lines[:2]) + "\n... (truncated special ext)"
            self.token_count += self._approx_token_count(snippet)
            return snippet

        # python => entire unless token_count>60000 => only def/class/return lines
        if ext == ".py":
            if self.token_count < 60000:
                self.token_count += self._approx_token_count(raw_text)
                return raw_text
            else:
                lines = raw_text.splitlines()
                pattern_def = re.compile(r'^\s*(def|class)\s+\w+.*:')
                pattern_return = re.compile(r'\breturn\b')
                snippet_lines = []
                for ln in lines:
                    if pattern_def.search(ln) or pattern_return.search(ln):
                        snippet_lines.append(ln)
                snippet = "\n".join(snippet_lines)
                snippet += "\n# (truncated python file due to token limit)"
                self.token_count += self._approx_token_count(snippet)
                return snippet

        # all other => entire unless token_count>65000 => skip
        if self.token_count < 65000:
            self.token_count += self._approx_token_count(raw_text)
            return raw_text
        else:
            return None

# ---------------------------------------------------------------------
# PreFlightManager
# ---------------------------------------------------------------------

class PreFlightManager:
    """
    Merges user code from /llm-output/input, does a Docker build+run with volume mount, 
    returns a PreFlightOutput (dir_tree, run_output).
    """
    def has_input_files(self) -> bool:
        input_dir = os.path.join(
            os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input"
        )
        if not os.path.isdir(input_dir):
            return False
        for _, _, files in os.walk(input_dir):
            if files:
                return True
        return False

    def perform_preflight_merge_and_run(self) -> PreFlightOutput:

        base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_folder = os.path.join(base_output_dir, f"preflight_{timestamp}")
        os.makedirs(run_folder, exist_ok=True)

        user_json = self._collect_input_files()
        if not user_json["dockerfile"].strip():
            user_json["dockerfile"] = """FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y python3 python3-pip
ENTRYPOINT ["python3","main.py"]
"""

        # Initialize Git
        gm = GitManager(run_folder)
        gm.merge_llm_changes(
            llm_dockerfile=user_json["dockerfile"],
            llm_files=user_json["files"]
        )

        # Docker build
        build_cmd = ["docker", "build", "-t", "preflight_app", run_folder]
        build_proc = subprocess.run(build_cmd, capture_output=True, text=True)
        dir_tree = run_tree_command(run_folder)
        if build_proc.returncode != 0:
            return PreFlightOutput(dir_tree=dir_tree, run_output=(build_proc.stderr or build_proc.stdout))

        # Docker run with volume mount
        run_cmd = [
            "docker", "run", "--rm",
            "-v", f"{run_folder}:/app",  # So if code writes new files, we see them
            "preflight_app"
        ]
        run_proc = subprocess.run(run_cmd, capture_output=True, text=True)
        dir_tree = run_tree_command(run_folder)
        if run_proc.returncode != 0:
            return PreFlightOutput(dir_tree=dir_tree, run_output=(run_proc.stderr or run_proc.stdout))

        return PreFlightOutput(dir_tree=dir_tree, run_output=run_proc.stdout)

    def _collect_input_files(self) -> Dict[str, Any]:
        """
        Gather code from /llm-output/input => {dockerfile, files[]}
        """
        input_dir = os.path.join(
            os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input"
        )
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
                if ".git" in full_path.lower():
                    continue
                try:
                    with open(full_path, "r", encoding="utf-8") as ff:
                        content = ff.read()
                except:
                    content = ""
                if fname.lower() == "dockerfile" and not dockerfile_contents:
                    dockerfile_contents = content
                else:
                    collected.append({"filename": rel_path, "content": content})

        return {"dockerfile": dockerfile_contents, "files": collected}
