# Copyright (C) 2024 Harrison E. Muchnic
# This program is licensed under the Affero General Public License (AGPL).
# See the LICENSE file for details.

# ./backend/src/functions/functions.py

from restack_ai.function import function, log
from dataclasses import dataclass
import os
import openai
import json
import tempfile
import subprocess
import difflib  # <--- NEW for patch generation

from pydantic import BaseModel
from typing import List, Optional

from src.prompts import current_generate_code_prompt, current_validate_output_prompt

openai.api_key = os.environ.get("OPENAI_KEY")

# Use the OpenAI Python SDK's structured output parsing
from openai import OpenAI
client = OpenAI(api_key=openai.api_key)

class FileItem(BaseModel):
    filename: str
    content: str
    class Config:
        extra = "forbid"

class GenerateCodeSchema(BaseModel):
    dockerfile: str
    files: List[FileItem]

class ValidateOutputSchema(BaseModel):
    result: bool
    dockerfile: Optional[str] = None
    files: Optional[List[FileItem]] = None

@dataclass
class GenerateCodeInput:
    user_prompt: str
    test_conditions: str

@dataclass
class GenerateCodeOutput:
    dockerfile: str
    files: list

@function.defn()
async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
    log.info("generate_code started", input=input)

    prompt = current_generate_code_prompt.format(
        user_prompt=input.user_prompt,
        test_conditions=input.test_conditions
    )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system", 
                "content": "You are the initial of an autonomous coding assistant agent. Generate complete code that will run."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        response_format=GenerateCodeSchema
    )

    result = completion.choices[0].message
    if result.refusal:
        raise RuntimeError("Model refused to generate code.")
    data = result.parsed

    files_list = [{"filename": f.filename, "content": f.content} for f in data.files]

    return GenerateCodeOutput(dockerfile=data.dockerfile, files=files_list)

@dataclass
class RunCodeInput:
    dockerfile: str
    files: list

@dataclass
class RunCodeOutput:
    output: str

@function.defn()
async def run_locally(input: RunCodeInput) -> RunCodeOutput:
    log.info("run_locally started", input=input)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        
        # Write Dockerfile
        with open(dockerfile_path, "w", encoding="utf-8") as f:
            f.write(input.dockerfile)
        
        # Write each file
        for file_item in input.files:
            file_path = os.path.join(temp_dir, file_item["filename"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as ff:
                ff.write(file_item["content"])
        
        # Build image
        build_cmd = ["docker", "build", "-t", "myapp", temp_dir]
        build_process = subprocess.run(build_cmd, capture_output=True, text=True)
        if build_process.returncode != 0:
            return RunCodeOutput(output=build_process.stderr or build_process.stdout)
        
        # Run container
        run_cmd = ["docker", "run", "--rm", "myapp"]
        run_process = subprocess.run(run_cmd, capture_output=True, text=True)
        if run_process.returncode != 0:
            return RunCodeOutput(output=run_process.stderr or run_process.stdout)
        
        return RunCodeOutput(output=run_process.stdout)

@dataclass
class ValidateOutputInput:
    dockerfile: str
    files: list
    output: str
    test_conditions: str

@dataclass
class ValidateOutputOutput:
    result: bool
    dockerfile: Optional[str] = None
    files: Optional[list] = None

@function.defn()
async def validate_output(input: ValidateOutputInput) -> ValidateOutputOutput:
    log.info("validate_output started", input=input)

    files_str = json.dumps(input.files, indent=2)

    validation_prompt = current_validate_output_prompt.format(
        test_conditions=input.test_conditions,
        dockerfile=input.dockerfile,
        files_str=files_str,
        output=input.output
    )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system", 
                "content": "You are an iteration of an autonomous coding assistant agent. If you change any files, provide complete file content replacements. Append a brief explanation at the bottom of readme.md about what you tried."
            },
            {
                "role": "user", 
                "content": validation_prompt
            }
        ],
        response_format=ValidateOutputSchema
    )

    result = completion.choices[0].message
    if result.refusal:
        return ValidateOutputOutput(result=False)

    data = result.parsed
    updated_files = [{"filename": f.filename, "content": f.content} for f in data.files] if data.files else None

    return ValidateOutputOutput(result=data.result, dockerfile=data.dockerfile, files=updated_files)

#
#  NEW HELPER FUNCTION to produce patch diffs
#

def create_diff(old_files: list, new_files: list) -> str:
    """
    Create a unified diff string from old_files to new_files.
    Each is a list of dict {filename:..., content:...}.
    """
    old_map = {f["filename"]: f["content"].splitlines(keepends=True) for f in old_files}
    new_map = {f["filename"]: f["content"].splitlines(keepends=True) for f in new_files}

    all_names = set(old_map.keys()) | set(new_map.keys())
    diff_text_parts = []

    for fname in sorted(all_names):
        old = old_map.get(fname, [])
        new = new_map.get(fname, [])
        diff = difflib.unified_diff(
            old, new,
            fromfile=f"a/{fname}",
            tofile=f"b/{fname}"
        )
        diff_str = "".join(diff)
        if diff_str.strip():
            diff_text_parts.append(diff_str)
    return "\n".join(diff_text_parts)
