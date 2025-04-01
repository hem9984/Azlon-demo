# ./backend/src/functions/functions.py
from restack_ai.function import function, log
from dataclasses import dataclass
import os
import openai
import json
import shutil
import subprocess
import re
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
            {"role": "system", "content": "You are the initial of an autonomous coding assistant agent. Generate complete code that will run."},
            {"role": "user", "content": prompt}
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

def validate_dockerfile(dockerfile: str) -> Tuple[bool, Optional[str]]:
    """
    Validate the Dockerfile for potentially malicious commands or configurations.
    Returns (is_valid, error_message)
    """
    # Check for prohibited instructions or patterns
    prohibited_patterns = [
        # Prevent privileged mode and host network
        r'--privileged',
        r'--net=host',
        # Prevent mounting sensitive host paths
        r'--volume\s+/:/|--volume=/:/|--volume\s+/etc|--volume=/etc|--volume\s+/var|--volume=/var',
        r'--mount.*source=/.*,',
        # Prevent adding capabilities
        r'--cap-add=ALL',
        r'--cap-add.*SYS_ADMIN',
        # Prevent dangerous exposed ports
        r'EXPOSE\s+22',
        # Prevent dangerous instructions
        r'FROM\s+.*--privileged',
    ]
    
    for pattern in prohibited_patterns:
        if re.search(pattern, dockerfile, re.IGNORECASE):
            return False, f"Dockerfile contains prohibited pattern: {pattern}"
    
    # Ensure the Dockerfile has a FROM instruction
    if not re.search(r'^\s*FROM\s+', dockerfile, re.MULTILINE):
        return False, "Dockerfile must contain a FROM instruction"
    
    return True, None

def validate_file_content(filename: str, content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate file content for potentially dangerous code patterns.
    Returns (is_valid, error_message)
    """
    # Skip validation for certain file types
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico')):
        return True, None
        
    # Python-specific checks
    if filename.endswith('.py'):
        # Check for potentially dangerous imports/uses
        dangerous_patterns = [
            r'import\s+os\.system', 
            r'import\s+subprocess',
            r'from\s+subprocess\s+import',
            r'__import__\([\'"]subprocess[\'"]\)',
            r'os\.system\(', 
            r'subprocess\.', 
            r'exec\(', 
            r'eval\(',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                return False, f"File {filename} contains potentially unsafe code pattern: {pattern}"
    
    # Shell script checks
    if filename.endswith('.sh') or filename == 'Dockerfile':
        dangerous_shell_patterns = [
            r'rm\s+-rf\s+/', 
            r'mkfs',
            r'dd\s+if=',
        ]
        
        for pattern in dangerous_shell_patterns:
            if re.search(pattern, content):
                return False, f"File {filename} contains potentially unsafe shell command: {pattern}"
    
    return True, None

@function.defn()
async def run_locally(input: RunCodeInput) -> RunCodeOutput:
    log.info("run_locally started", input=input)
    
    # Validate Dockerfile
    valid, error_msg = validate_dockerfile(input.dockerfile)
    if not valid:
        return RunCodeOutput(output=f"Security validation failed: {error_msg}")
    
    # Validate files
    for file_item in input.files:
        valid, error_msg = validate_file_content(file_item["filename"], file_item["content"])
        if not valid:
            return RunCodeOutput(output=f"Security validation failed: {error_msg}")
    
    # Decide where to put the files
    base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    
    # Create a unique subfolder each run
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
        # Ensure the file path doesn't try to escape the run folder
        if os.path.normpath(file_path).startswith(os.path.normpath(run_folder)):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as ff:
                ff.write(file_item["content"])
                log.info(f"Writing file {file_item['filename']} to {file_path}")
        else:
            return RunCodeOutput(output=f"Security validation failed: File path {file_item['filename']} attempting to escape container directory")
    
    # Run docker build with timeout
    build_cmd = ["docker", "build", "-t", f"myapp_{timestamp}", run_folder]
    try:
        build_process = subprocess.run(
            build_cmd, 
            capture_output=True, 
            text=True, 
            timeout=60  # 60-second timeout for build
        )
        if build_process.returncode != 0:
            return RunCodeOutput(output=build_process.stderr or build_process.stdout)
    except subprocess.TimeoutExpired:
        return RunCodeOutput(output="Docker build timed out after 60 seconds")
    
    # Run the container with security constraints
    run_cmd = [
        "docker", "run",
        "--rm",                     # Remove container after run
        "--read-only",              # Make filesystem read-only
        "--network=none",           # No network access
        "--memory=512m",            # Memory limit
        "--memory-swap=512m",       # Prevent swap usage
        "--cpus=0.5",               # CPU limit
        "--cap-drop=ALL",           # Drop all capabilities
        "--security-opt=no-new-privileges", # Prevent privilege escalation
        f"myapp_{timestamp}"       # Use timestamped image name
    ]
    try:
        run_process = subprocess.run(
            run_cmd, 
            capture_output=True, 
            text=True,
            timeout=30  # 30-second timeout for execution
        )
        if run_process.returncode != 0:
            return RunCodeOutput(output=run_process.stderr or run_process.stdout)
    except subprocess.TimeoutExpired:
        return RunCodeOutput(output="Docker run timed out after 30 seconds")
    
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