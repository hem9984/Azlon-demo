# Copyright (C) 2024 Harrison E. Muchnic
# This program is licensed under the Affero General Public License (AGPL).
# See the LICENSE file for details.

# src/functions/functions.py
from restack_ai.function import function, log
from dataclasses import dataclass
import os
import openai
import json
import tempfile
import subprocess

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

@function.defn()
async def run_locally(input: RunCodeInput) -> RunCodeOutput:
    log.info("run_locally started", input=input)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        
        # Write the Dockerfile
        with open(dockerfile_path, "w", encoding="utf-8") as f:
            f.write(input.dockerfile)
        
        # Write each file
        for file_item in input.files:
            file_path = os.path.join(temp_dir, file_item["filename"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as ff:
                ff.write(file_item["content"])
        
        # Build the Docker image
        build_cmd = ["docker", "build", "-t", "myapp", temp_dir]
        build_process = subprocess.run(build_cmd, capture_output=True, text=True)
        if build_process.returncode != 0:
            return RunCodeOutput(output=build_process.stderr or build_process.stdout)
        
        # Run the Docker container
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


# # Copyright (C) 2024 Harrison E. Muchnic
# # This program is licensed under the Affero General Public License (AGPL).
# # See the LICENSE file for details.

# # src/functions/functions.py
# from restack_ai.function import function, log
# from dataclasses import dataclass
# import os
# import openai
# import json
# import shutil
# import subprocess
# from datetime import datetime

# from pydantic import BaseModel
# from typing import List, Optional

# from src.prompts import current_generate_code_prompt, current_validate_output_prompt

# openai.api_key = os.environ.get("OPENAI_KEY")

# # Use the OpenAI Python SDK's structured output parsing
# from openai import OpenAI
# client = OpenAI(api_key=openai.api_key)

# class FileItem(BaseModel):
#     filename: str
#     content: str

#     class Config:
#         extra = "forbid"
#         schema_extra = {
#             "type": "object",
#             "properties": {
#                 "filename": {"type": "string"},
#                 "content": {"type": "string"}
#             },
#             "required": ["filename", "content"],
#             "additionalProperties": False
#         }

# class GenerateCodeSchema(BaseModel):
#     dockerfile: str
#     files: List[FileItem]
    
#     class Config:
#         extra = "forbid"
#         schema_extra = {
#             "type": "object",
#             "properties": {
#                 "dockerfile": {"type": "string"},
#                 "files": {
#                     "type": "array",
#                     "items": {"$ref": "#/$defs/FileItem"}
#                 }
#             },
#             "required": ["dockerfile", "files"],
#             "additionalProperties": False,
#             "$defs": {
#                 "FileItem": {
#                     "type": "object",
#                     "properties": {
#                         "filename": {"type": "string"},
#                         "content": {"type": "string"}
#                     },
#                     "required": ["filename", "content"],
#                     "additionalProperties": False
#                 }
#             }
#         }

# class ValidateOutputSchema(BaseModel):
#     result: bool
#     dockerfile: Optional[str] = None
#     files: Optional[List[FileItem]] = None
    
#     class Config:
#         extra = "forbid"
#         schema_extra = {
#             "type": "object",
#             "properties": {
#                 "result": {"type": "boolean"},
#                 "dockerfile": {
#                     "anyOf": [
#                         {"type": "string"},
#                         {"type": "null"}
#                     ]
#                 },
#                 "files": {
#                     "anyOf": [
#                         {
#                             "type": "array",
#                             "items": {"$ref": "#/$defs/FileItem"}
#                         },
#                         {"type": "null"}
#                     ]
#                 }
#             },
#             "required": ["result", "dockerfile", "files"],
#             "additionalProperties": False,
#             "$defs": {
#                 "FileItem": {
#                     "type": "object",
#                     "properties": {
#                         "filename": {"type": "string"},
#                         "content": {"type": "string"}
#                     },
#                     "required": ["filename", "content"],
#                     "additionalProperties": False
#                 }
#             }
#         }


# @dataclass
# class GenerateCodeInput:
#     user_prompt: str
#     test_conditions: str

# @dataclass
# class GenerateCodeOutput:
#     dockerfile: str
#     files: list

# @function.defn()
# async def generate_code(input: GenerateCodeInput) -> GenerateCodeOutput:
#     log.info("generate_code started", input=input)

#     prompt = current_generate_code_prompt.format(
#         user_prompt=input.user_prompt,
#         test_conditions=input.test_conditions
#     )

#     completion = client.beta.chat.completions.parse(
#         model="gpt-4o-2024-08-06",
#         messages=[
#             {"role": "system", "content": "You are the initial of an autonomous coding assistant agent. Generate complete code that will run."},
#             {"role": "user", "content": prompt}
#         ],
#         response_format=GenerateCodeSchema
#     )

#     result = completion.choices[0].message
#     if result.refusal:
#         raise RuntimeError("Model refused to generate code.")
#     data = result.parsed

#     files_list = [{"filename": f.filename, "content": f.content} for f in data.files]

#     return GenerateCodeOutput(dockerfile=data.dockerfile, files=files_list)


# @dataclass
# class RunCodeInput:
#     dockerfile: str
#     files: list

# @dataclass
# class RunCodeOutput:
#     output: str

# @function.defn()
# async def run_locally(input: RunCodeInput) -> RunCodeOutput:
#     log.info("run_locally started", input=input)
    
#     # Decide where to put the files. If not set, fall back to /tmp or /app/output
#     base_output_dir = os.environ.get("LLM_OUTPUT_DIR", "/app/output")
    
#     # For clarity, create a unique subfolder each run (timestamp-based):
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     run_folder = os.path.join(base_output_dir, f"llm_run_{timestamp}")
#     os.makedirs(run_folder, exist_ok=True)
    
#     # Write the Dockerfile
#     dockerfile_path = os.path.join(run_folder, "Dockerfile")
#     with open(dockerfile_path, "w", encoding="utf-8") as f:
#         f.write(input.dockerfile)
    
#     # Write each file
#     for file_item in input.files:
#         file_path = os.path.join(run_folder, file_item["filename"])
#         os.makedirs(os.path.dirname(file_path), exist_ok=True)
#         with open(file_path, "w", encoding="utf-8") as ff:
#             ff.write(file_item["content"])
    
#     # Now run docker build, connecting to Docker-in-Docker at DOCKER_HOST
#     build_cmd = ["docker", "build", "-t", "myapp", run_folder]
#     build_process = subprocess.run(build_cmd, capture_output=True, text=True)
#     if build_process.returncode != 0:
#         return RunCodeOutput(output=build_process.stderr or build_process.stdout)
    
#     # Then run the container
#     run_cmd = ["docker", "run", "--rm", "myapp"]
#     run_process = subprocess.run(run_cmd, capture_output=True, text=True)
#     if run_process.returncode != 0:
#         return RunCodeOutput(output=run_process.stderr or run_process.stdout)
    
#     return RunCodeOutput(output=run_process.stdout)


# @dataclass
# class ValidateOutputInput:
#     dockerfile: str
#     files: list
#     output: str
#     test_conditions: str

# @dataclass
# class ValidateOutputOutput:
#     result: bool
#     dockerfile: Optional[str] = None
#     files: Optional[list] = None

# @function.defn()
# async def validate_output(input: ValidateOutputInput) -> ValidateOutputOutput:
#     log.info("validate_output started", input=input)

#     files_str = json.dumps(input.files, indent=2)

#     validation_prompt = current_validate_output_prompt.format(
#         test_conditions=input.test_conditions,
#         dockerfile=input.dockerfile,
#         files_str=files_str,
#         output=input.output
#     )

#     completion = client.beta.chat.completions.parse(
#         model="gpt-4o-2024-08-06",
#         messages=[
#             {"role": "system", "content": "You are an iteration of an autonomous coding assistant agent. If you change any files, provide complete file content replacements. Append a brief explanation at the bottom of readme.md about what you tried."},
#             {"role": "user", "content": validation_prompt}
#         ],
#         response_format=ValidateOutputSchema
#     )

#     result = completion.choices[0].message
#     if result.refusal:
#         return ValidateOutputOutput(result=False)

#     data = result.parsed
#     updated_files = [{"filename": f.filename, "content": f.content} for f in data.files] if data.files is not None else None

#     return ValidateOutputOutput(result=data.result, dockerfile=data.dockerfile, files=updated_files)
