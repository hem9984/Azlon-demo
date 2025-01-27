#./backend/src/utils/file_handling.py
import os
import re
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
    configures user name/email to allow committing.
    """
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "AzlonBot"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "azlon@local"], cwd=repo_path, check=True)

def commit_all_changes(repo_path: str, message: str) -> None:
    """
    Adds all files in repo_path to staging and commits with the given message.
    """
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True)

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
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo_path, check=True)
    commit_all_changes(repo_path, "Base commit")

    subprocess.run(["git", "checkout", "-b", "llm-changes"], cwd=repo_path, check=True)

    for f in llm_files:
        full_path = os.path.join(repo_path, f["filename"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as file_out:
            file_out.write(f["content"])

    commit_all_changes(repo_path, "LLM changes")

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
    """
    base_input_dir = os.path.join(
        os.environ.get("LLM_OUTPUT_DIR", "/app/output"), "input"
    )
    dockerfile_contents = ""
    collected_files = []

    if not os.path.isdir(base_input_dir):
        return {"dockerfile": "", "files": []}

    for root, dirs, files in os.walk(base_input_dir):
        for fname in files:
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
    Example: 'def my_func(...):' or 'class MyClass:'
    """
    signatures = []
    pattern = re.compile(r'^\s*(def|class)\s+\w+.*:')
    for line in content.splitlines():
        if pattern.match(line):
            signatures.append(line.strip())
    if not signatures:
        return "# (No function/class definitions found)"
    return "\n".join(signatures)

def build_files_str(dockerfile: str, files: List[Dict[str, str]], iteration: int) -> str:
    """
    For the 'validate_output' step, build a JSON-like string representing
    the current Dockerfile + code, either partially or fully:
      - For iteration < 6 => partial approach to avoid token overload
      - For iteration >= 6 => full content of every file
      - If file ends with .csv, .numpy, etc => only first 2 lines + ...
      - If text file has > 50 lines in iteration < 6 => only function/class signatures
    """
    # If iteration >= 6 => we supply everything
    if iteration >= 6:
        return json.dumps(
            [
                {"filename": "Dockerfile", "content": dockerfile}
            ]
            + files,
            indent=2
        )

    # iteration < 6 => partial
    # We'll produce a Python list of {filename, content} but with truncated contents if large or if it's a special extension
    truncated_list = []

    special_exts = {".csv", ".numpy", ".npy", ".tsv"}

    for f in files:
        ext = os.path.splitext(f["filename"])[1].lower()
        content_lines = f["content"].splitlines()

        # special extension => only first 2 lines
        if ext in special_exts:
            snippet = "\n".join(content_lines[:2]) + "\n..."
            truncated_list.append({
                "filename": f["filename"],
                "content": snippet
            })
            continue

        # normal text file => if > 50 lines, show only function signatures
        if len(content_lines) > 50:
            sigs = extract_function_signatures(f["content"])
            snippet = "# (File truncated for brevity)\n" + sigs
            truncated_list.append({
                "filename": f["filename"],
                "content": snippet
            })
        else:
            # <= 50 lines => keep entire content
            truncated_list.append({
                "filename": f["filename"],
                "content": f["content"]
            })

    # Also handle Dockerfile the same way: if iteration < 6, we can show partial or full?
    dockerfile_lines = dockerfile.splitlines()
    if len(dockerfile_lines) > 50:
        # Typically Dockerfiles are short, but just in case
        snippet = "\n".join(dockerfile_lines[:10]) + "\n# (Dockerfile truncated)"
        docker_obj = {"filename": "Dockerfile", "content": snippet}
    else:
        docker_obj = {"filename": "Dockerfile", "content": dockerfile}

    final_list = [docker_obj] + truncated_list

    return json.dumps(final_list, indent=2)
