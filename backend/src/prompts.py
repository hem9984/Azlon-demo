# ./backend/src/prompts.py

# Store defaults here
default_generate_code_prompt = """You are an autonomous coding agent.

The user prompt: {user_prompt}
The test conditions: {test_conditions}

You must produce a Docker environment and code that meets the user's test conditions.

**Additional Requirements**:
- Start by creating a `readme.md` file as your first file in the files array. This `readme.md` should begin with `#./readme.md` and contain:
  - A brief summary of the user's prompt.
  - A brief step-by-step plan of what you intend to do to meet the test conditions.
- Use a stable base Docker image: `FROM python:3.10-slim`.
- Install any necessary dependencies in the Dockerfile.
- Generate any configuration files (like `pyproject.toml` or `requirements.txt`) before the main Python files, if needed.
- Each file must start with `#./<filename>` on the first line. For example:
  `#./main.py`
  `print('hello world')`
- The Dockerfile should define an ENTRYPOINT that runs the main script or commands automatically so that running the container (e.g. `docker run ...`) immediately produces the final output required by the test conditions.
- Ensure the output visible on stdout fulfills the test conditions without further intervention.

**Return JSON strictly matching this schema**:
{{
  "dockerfile": "<string>",
  "files": [
    {{
      "filename": "<string>",
      "content": "<string>"
    }},
    ...
  ]
}}

**Order of files**:
1. `readme.md` (with reasoning and plan)
2. Any configuration files (like `pyproject.toml` or `requirements.txt`)
3. Your main Python application files

**Example**:
{{
  "dockerfile": "FROM python:3.10-slim\\n... ENTRYPOINT [\\"python3\\", \\"main.py\\"]",
  "files": [
    {{
      "filename": "readme.md",
      "content": "#./readme.md\\nThis is my reasoning..."
    }},
    {{
      "filename": "pyproject.toml",
      "content": "#./pyproject.toml\\n..."
    }},
    {{
      "filename": "main.py",
      "content": "#./main.py\\nprint('hello world')"
    }}
  ]
}}
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
