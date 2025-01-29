# ./backend/src/prompts.py

# Store defaults here
default_generate_code_prompt = """
You are an autonomous coding agent. Generate complete code that will run.

Given the following requirements:
- Start with a readme.md containing a summary and step-by-step plan
- Use python:3.10-slim as base Docker image
- Install necessary dependencies in Dockerfile
- Each file should start with #./<filename>
- Dockerfile should define ENTRYPOINT to run automatically
- Output must be visible on stdout without intervention
- Files should be ordered: readme.md, config files, main application files
"""

default_validate_output_prompt = """The test conditions: {test_conditions}

dockerfile:
{dockerfile}

files:
{files_str}

output:
{output}

If all test conditions are met, return exactly:
{{ "result": true, "dockerfile": null, "files": null }}

Otherwise (if you need to fix or add files, modify the dockerfile, etc.), return exactly:
{{
  "result": false,
  "dockerfile": "FROM python:3.10-slim\\n...",
  "files": [
    {{
      "filename": "filename.ext",
      "content": "#./filename.ext\\n..."
    }}
  ]
}}

You may add, remove, or modify multiple files as needed when returning false. Just ensure you follow the same schema and format strictly. Do not add extra commentary or keys.
If returning null for dockerfile or files, use JSON null, not a string."""

# Storing the current prompts in memory for simplicity.
current_generate_code_prompt = default_generate_code_prompt
current_validate_output_prompt = default_validate_output_prompt

def get_prompts():
    return {
        "generate_code_prompt": current_generate_code_prompt,
        "validate_output_prompt": current_validate_output_prompt
    }

def set_prompts(generate_code_prompt: str, validate_output_prompt: str):
    global current_generate_code_prompt, current_validate_output_prompt
    current_generate_code_prompt = generate_code_prompt
    current_validate_output_prompt = validate_output_prompt
