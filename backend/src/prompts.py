# backend/src/prompts.py

# Store defaults here
default_generate_code_prompt = """<create a prompt here>
"""

default_validate_output_prompt = """<create a prompt here>"""

# we will need more prompts given that we now have 2 workflows and a specific strategy that we need to make prompts for

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
