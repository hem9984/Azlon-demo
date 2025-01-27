#./backend/src/utils/file_handling.py
import os
import re
import json
import subprocess
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------
# Git & tree utilities
# ---------------------------------------

def run_tree_command(directory: str) -> str:
    """
    Runs the `tree` command against the given directory
    and returns its stdout as a string.
    """
    try:
        result = subprocess.run(
            ["tree", directory],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except Exception as e:
        logger.warning(f"Failed to run 'tree' in {directory}: {e}")
        return ""

def initialize_git_repo(repo_path: str) -> None:
    """
    Initializes a new Git repository in repo_path,
    using 'main' as the default branch to avoid warnings.
    Configures user name/email to allow committing.
    """
    # The key argument is --initial-branch=main
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "AzlonBot"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "azlon@local"], cwd=repo_path, check=True)

def commit_all_changes(repo_path: str, message: str, allow_empty: bool = True) -> None:
    """
    Adds all files in repo_path to staging and commits with the given message.
    If allow_empty=True, we pass --allow-empty so it won't fail if no changes exist.
    """
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    commit_cmd = ["git", "commit", "-m", message]
    if allow_empty:
        commit_cmd.append("--allow-empty")
    subprocess.run(commit_cmd, cwd=repo_path, check=True)

def auto_merge_with_llm_changes(repo_path: str) -> None:
    """
    Merges the 'llm-changes' branch into the 'main' branch
    with automatic conflict resolution favoring the LLM changes.
    """
    subprocess.run(
        ["git", "merge", "llm-changes", "-X", "theirs", "--allow-unrelated-histories"],
        cwd=repo_path,
        check=True
    )

def prepare_codebase_merge(repo_path: str, llm_files: List[Dict[str, str]]) -> None:
    """
    1) Commits existing (base) code on 'main'
    2) Creates & switches to 'llm-changes'
    3) Writes the new LLM files, commits them
    4) Switches back to 'main', merges with 'llm-changes' (favor LLM)
    """
    # We are already on 'main' from initialize_git_repo, but let's forcibly check out:
    subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)
    commit_all_changes(repo_path, "Base commit", allow_empty=True)

    # Create or switch to 'llm-changes' branch
    subprocess.run(["git", "checkout", "-b", "llm-changes"], cwd=repo_path, check=True)

    for f in llm_files:
        full_path = os.path.join(repo_path, f["filename"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as file_out:
            file_out.write(f["content"])

    commit_all_changes(repo_path, "LLM changes", allow_empty=True)

    subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)
    auto_merge_with_llm_changes(repo_path)

# ---------------------------------------
# Collect user input code
# ---------------------------------------

def collect_input_files() -> Dict[str, any]:
    """
    Scans ./llm-output/input and returns a dict:
    {
      "dockerfile": <str or empty if none found>,
      "files": [ { "filename": "path/file", "content": "..." }, ... ]
    }
    We skip any .git directories or their contents.
    """
    base_input_dir = os.path.join(
        os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input"
    )
    dockerfile_contents = ""
    collected_files = []

    if not os.path.isdir(base_input_dir):
        return {"dockerfile": "", "files": []}

    for root, dirs, files in os.walk(base_input_dir):
        # skip any .git directories
        if ".git" in dirs:
            dirs.remove(".git")

        for fname in files:
            # If it's in a .git folder deeper, skip
            if ".git" in root:
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, base_input_dir)

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except:
                content = ""

            if fname.lower() == "dockerfile":
                if not dockerfile_contents:
                    dockerfile_contents = content
            else:
                collected_files.append({
                    "filename": rel_path,
                    "content": content
                })

    return {
        "dockerfile": dockerfile_contents,
        "files": collected_files
    }

# ---------------------------------------
# Summaries & partial code handling
# ---------------------------------------

def extract_function_signatures(content: str) -> str:
    """
    Return lines that look like function or class definitions.
    E.g. 'def my_func(...):' or 'class MyClass:'
    """
    pattern = re.compile(r'^\s*(def|class)\s+\w+.*:')
    signatures = []
    for line in content.splitlines():
        if pattern.match(line):
            signatures.append(line.strip())
    if not signatures:
        return "# (No function/class definitions found)"
    return "\n".join(signatures)

def build_files_str(dockerfile: str, files: List[Dict[str, str]], iteration: int) -> str:
    """
    For 'validate_output':
      - iteration >= 6 => full content of Dockerfile + files
      - iteration < 6 => partial
        * If file ext in {".csv",".numpy",".npy",".tsv"} => only first 2 lines + '...'
        * If > 50 lines => function/class signatures only
    Returns a JSON array string that we inject into the prompt.
    """
    if iteration >= 6:
        return json.dumps(
            [{"filename": "Dockerfile", "content": dockerfile}] + files,
            indent=2
        )

    special_exts = {".csv", ".numpy", ".npy", ".tsv"}
    truncated_list = []

    for f in files:
        ext = os.path.splitext(f["filename"])[1].lower()
        lines = f["content"].splitlines()

        # If it's a special extension, only first 2 lines
        if ext in special_exts:
            snippet = "\n".join(lines[:2]) + "\n..." if len(lines) >= 2 else "... (no lines found)"
            truncated_list.append({
                "filename": f["filename"],
                "content": snippet
            })
            continue

        # If it's > 50 lines, only function/class signatures
        if len(lines) > 50:
            sigs = extract_function_signatures(f["content"])
            snippet = "# (File truncated for brevity)\n" + sigs
            truncated_list.append({
                "filename": f["filename"],
                "content": snippet
            })
        else:
            truncated_list.append({
                "filename": f["filename"],
                "content": f["content"]
            })

    docker_lines = dockerfile.splitlines()
    if len(docker_lines) > 50:
        df_snippet = "\n".join(docker_lines[:10]) + "\n# (Dockerfile truncated)"
    else:
        df_snippet = dockerfile

    final_list = [{"filename": "Dockerfile", "content": df_snippet}] + truncated_list
    return json.dumps(final_list, indent=2)
