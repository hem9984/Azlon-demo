# ./backend/src/functions/functions.py
from restack_ai.function import function, log
from dataclasses import dataclass
import os
import openai
import json
import shutil
import subprocess
from datetime import datetime

from pydantic import BaseModel
from typing import List, Optional, Tuple

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
        schema_extra = {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["filename", "content"],
            "additionalProperties": False
        }

class GenerateCodeSchema(BaseModel):
    dockerfile: str
    files: List[FileItem]
    
    class Config:
        extra = "forbid"
        schema_extra = {
            "type": "object",
            "properties": {
                "dockerfile": {"type": "string"},
                "files": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/FileItem"}
                }
            },
            "required": ["dockerfile", "files"],
            "additionalProperties": False,
            "$defs": {
                "FileItem": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["filename", "content"],
                    "additionalProperties": False
                }
            }
        }

class ValidateOutputSchema(BaseModel):
    result: bool
    dockerfile: Optional[str] = None
    files: Optional[List[FileItem]] = None
    
    class Config:
        extra = "forbid"
        schema_extra = {
            "type": "object",
            "properties": {
                "result": {"type": "boolean"},
                "dockerfile": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ]
                },
                "files": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {"$ref": "#/$defs/FileItem"}
                        },
                        {"type": "null"}
                    ]
                }
            },
            "required": ["result", "dockerfile", "files"],
            "additionalProperties": False,
            "$defs": {
                "FileItem": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["filename", "content"],
                    "additionalProperties": False
                }
            }
        }


@dataclass
class GenerateCodeInput:
    user_prompt: str
    test_conditions: str

@dataclass
class GenerateCodeOutput:
    dockerfile: str
    files: list

def validate_generated_code_security(dockerfile: str, files: list) -> Tuple[bool, str]:
    """
    Validate the security of generated code and Dockerfile.
    
    Args:
        dockerfile: The generated Dockerfile content
        files: List of generated code files with their content
        
    Returns:
        tuple: (is_safe, reason)
            - is_safe: Boolean indicating if the code is safe
            - reason: Explanation of why the code is unsafe if applicable
    """
    # Check Dockerfile for potentially dangerous commands
    dangerous_docker_commands = [
        "chmod 777", "--privileged", "sudo", 
        "curl | bash", "wget | bash", 
        "VOLUME /", "VOLUME /etc", "VOLUME /var", "VOLUME /bin", "VOLUME /usr",
        "EXPOSE 22", "COPY id_rsa", "COPY authorized_keys"
    ]
    
    for cmd in dangerous_docker_commands:
        if cmd in dockerfile:
            return False, f"Dockerfile contains potentially dangerous command: {cmd}"
    
    # Define language-specific patterns
    python_patterns = [
        "os.system(", "subprocess.call(", "subprocess.run(", "subprocess.Popen(", 
        "eval(", "exec(", "__import__(", 
        "pickle.load(", "marshal.loads(", "yaml.load(", "yaml.unsafe_load(",
        "shutil.rmtree(", "os.remove(", "os.unlink("
    ]
    
    js_patterns = [
        "eval(", "Function(", "setTimeout(", "setInterval(", 
        "require('child_process')", "spawn(", "exec(", 
        "fs.rmdir(", "fs.unlink("
    ]
    
    # Check files based on their extension
    for file_item in files:
        filename = file_item["filename"]
        content = file_item["content"]
        
        # Skip validation for test files and documentation
        if (filename.startswith("test_") or filename.endswith("_test.py") or 
            filename.endswith(".md") or filename.endswith(".txt") or 
            filename == "README.md" or filename == "LICENSE"):
            continue
        
        # Apply language-specific patterns
        patterns_to_check = []
        if filename.endswith(".py"):
            patterns_to_check = python_patterns
        elif filename.endswith(".js") or filename.endswith(".jsx"):
            patterns_to_check = js_patterns
        # Add more language-specific patterns as needed
        
        # Check for sensitive paths regardless of file type
        sensitive_paths = [
            "/.ssh", "/etc/passwd", "/etc/shadow", "/root/", "/.bash_history"
        ]
        
        for path in sensitive_paths:
            if path in content:
                return False, f"File {filename} contains sensitive path: {path}"
        
        # Check language-specific patterns
        for pattern in patterns_to_check:
            if pattern in content:
                # Basic context check - could be improved with proper parsing
                # Check if pattern is in a comment line
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if pattern in line:
                        # Skip if line is a comment (simplified check)
                        if (filename.endswith(".py") and line.strip().startswith("#")) or \
                           ((filename.endswith(".js") or filename.endswith(".jsx")) and (line.strip().startswith("//") or line.strip().startswith("/*"))):
                            continue
                        
                        return False, f"File {filename} contains potentially dangerous pattern: {pattern}"
    
    return True, ""

@function.defn()
async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
    log.info("generate_code started", input=input)

    prompt = current_generate_code_prompt.format(
        user_prompt=input.user_prompt,
        test_conditions=input.test_conditions
    )

    # Enhance the system prompt with specific security instructions
    system_prompt = (
        "You are an autonomous coding assistant agent. Generate complete code that will run. "
        "Follow secure coding practices and avoid using dangerous operations such as: "
        "- Arbitrary command execution (e.g., os.system, subprocess.call, eval, exec) "
        "- Unrestricted file operations (e.g., open with write access to sensitive paths) "
        "- Network access without proper validation "
        "- Privileged operations in Dockerfiles "
    )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format=GenerateCodeSchema
    )

    result = completion.choices[0].message
    if result.refusal:
        raise RuntimeError("Model refused to generate code.")
    data = result.parsed

    files_list = [{"filename": f.filename, "content": f.content} for f in data.files]
    
    # Validate the generated code for security issues
    is_safe, reason = validate_generated_code_security(data.dockerfile, files_list)
    if not is_safe:
        raise RuntimeError(f"Security validation failed: {reason}")

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
    
    # Decide where to put the files. If not set, fall back to /tmp or /app/output
    base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    
    # For clarity, create a unique subfolder each run (timestamp-based):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(base_output_dir, f"llm_run_{timestamp}")
    os.makedirs(run_folder, exist_ok=True)
    
    # Write the Dockerfile
    dockerfile_path = os.path.join(run_folder, "Dockerfile")
    with open(dockerfile_path, "w", encoding="utf-8") as f:
        f.write(input.dockerfile)
    
    # Write each file
    for file_item in input.files:
        file_path = os.path.join(run_folder, file_item["filename"])
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as ff:
            ff.write(file_item["content"])
            log.info(f"Writing file {file_item['filename']} to {file_path}")
    
    # Now run docker build, connecting to Docker-in-Docker at DOCKER_HOST
    build_cmd = ["docker", "build", "-t", "myapp", run_folder]
    build_process = subprocess.run(build_cmd, capture_output=True, text=True)
    if build_process.returncode != 0:
        return RunCodeOutput(output=build_process.stderr or build_process.stdout)
    
    # Then run the container
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
            {"role": "system", "content": "You are an iteration of an autonomous coding assistant agent. If you change any files, provide complete file content replacements. Append a brief explanation at the bottom of readme.md about what you tried."},
            {"role": "user", "content": validation_prompt}
        ],
        response_format=ValidateOutputSchema
    )

    result = completion.choices[0].message
    if result.refusal:
        return ValidateOutputOutput(result=False)

    data = result.parsed
    updated_files = [{"filename": f.filename, "content": f.content} for f in data.files] if data.files is not None else None

    return ValidateOutputOutput(result=data.result, dockerfile=data.dockerfile, files=updated_files)