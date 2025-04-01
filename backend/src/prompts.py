# ./backend/src/prompts.py

import re
import html

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

def sanitize_input(input_str):
    """
    Sanitize user inputs to prevent prompt injection attacks.
    
    Args:
        input_str: String to sanitize
        
    Returns:
        Sanitized string
    """
    if input_str is None:
        return ""
    
    # Convert to string if it's not already
    input_str = str(input_str)
    
    # Escape HTML entities to prevent HTML injection
    input_str = html.escape(input_str)
    
    # Remove potential prompt injection patterns
    # These are patterns that might be used to hijack or manipulate the AI's behavior
    injection_patterns = [
        r'ignore previous instructions',
        r'disregard (all|previous) instructions',
        r'new instruction:',
        r'system prompt:',
        r'you are now',
        r'forget (all|previous)'
    ]
    
    for pattern in injection_patterns:
        input_str = re.sub(pattern, "[FILTERED]", input_str, flags=re.IGNORECASE)
    
    return input_str

def get_safe_prompts(user_prompt, test_conditions):
    """
    Generate safe prompts with sanitized user inputs.
    
    Args:
        user_prompt: User prompt to include in the code generation prompt
        test_conditions: Test conditions to include in the prompts
        
    Returns:
        Dictionary containing safe prompts
    """
    # Sanitize inputs
    safe_user_prompt = sanitize_input(user_prompt)
    safe_test_conditions = sanitize_input(test_conditions)
    
    # Format the generate code prompt with sanitized inputs
    safe_generate_code_prompt = current_generate_code_prompt.format(
        user_prompt=safe_user_prompt,
        test_conditions=safe_test_conditions
    )
    
    # Do not format validate_output_prompt here as it requires additional parameters
    
    return {
        "generate_code_prompt": safe_generate_code_prompt,
        "validate_output_prompt": current_validate_output_prompt,
        "test_conditions": safe_test_conditions  # Keep the sanitized test_conditions for later use
    }

def format_validate_output_prompt(test_conditions, dockerfile, files_str, output):
    """
    Format the validate output prompt with sanitized inputs.
    
    Args:
        test_conditions: Test conditions to include in the prompt
        dockerfile: Dockerfile content to validate
        files_str: String representation of files to validate
        output: Output to validate
        
    Returns:
        Formatted validate output prompt
    """
    # Sanitize inputs
    safe_test_conditions = sanitize_input(test_conditions)
    safe_dockerfile = sanitize_input(dockerfile)
    safe_files_str = sanitize_input(files_str)
    safe_output = sanitize_input(output)
    
    # Format the prompt with sanitized inputs
    return current_validate_output_prompt.format(
        test_conditions=safe_test_conditions,
        dockerfile=safe_dockerfile,
        files_str=safe_files_str,
        output=safe_output
    )

def get_prompts():
    """
    Get the current prompt templates (not formatted with user inputs).
    
    Returns:
        Dictionary containing the current prompt templates
    """
    return {
        "generate_code_prompt": current_generate_code_prompt,
        "validate_output_prompt": current_validate_output_prompt
    }

def set_prompts(generate_code_prompt, validate_output_prompt):
    """
    Set new prompt templates.
    
    Args:
        generate_code_prompt: New generate code prompt template
        validate_output_prompt: New validate output prompt template
    """
    global current_generate_code_prompt, current_validate_output_prompt
    current_generate_code_prompt = generate_code_prompt
    current_validate_output_prompt = validate_output_prompt