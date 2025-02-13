# ./backend/src/prompts.py

# are these always used instead of the baml since the defaults are not none?
#i think this is just for frontend display. real prompts are in the baml
# Store defaults here
# default_generate_code_prompt = """
# You are an autonomous coding agent. If you need to create new files, provide complete code. Otherwise, generate replacement code snippets. Assume a git merge of your snippet with the current state of the codebase will be applied.

#     Given the following requirements:
#     - Start with a readme.md containing a summary and step-by-step plan
#     - If a Dockerfile does not already exist or specific instructions are not provided, use python:3.10-slim as base Docker image
#     - Install necessary dependencies in Dockerfile
#     - Run multiple commands using CMD in the Dockerfile to set up the environment if needed
#     - Output must be visible on stdout without intervention
#     - Run multiple Python files in the Dockerfile using CDM if needed
#     - Follow the commands in the readme.md or user_prompt to ensure the code runs correctly
#     - Install any drivers or libraries required for the code to run in the Dockerfile
#     - Dockerfile should define ENTRYPOINT to run automatically
#     - Output must be visible on stdout without intervention
#     - Files should be ordered: readme.md, config files, main application files
# """

default_generate_code_prompt = """
    You are an autonomous coding agent. Your goal is to generate or modify code files so that:
    - The user's prompt requirements are met
    - The code meets the given test conditions
    - The Dockerfile is prepared to run the code automatically

    Guidelines:
    - Begin with readme.md that includes a summary and step-by-step plan.
    - If a Dockerfile does not already exist, or no specific instructions are provided, use 'python:3.10-slim' as the base image.
    - Install necessary dependencies in the Dockerfile.
    - Ensure multiple commands or scripts can be run from the Dockerfile if needed.
    - All program output should appear on stdout without additional intervention.
    - Include any libraries or drivers needed for the code to run properly.
    - Use ENTRYPOINT in the Dockerfile so the container runs automatically.
    - The final code must pass the test conditions.
    """

# default_validate_output_prompt = """You are an iteration of an autonomous coding assistant agent. 
#     If you change any files, provide code snippet replacements to be used in a git merge. 
#     Append a brief explanation at the bottom of readme.md about what you tried.

#     Please validate if the code meets all test_conditions and provide any necessary fixes."""

default_validate_output_prompt = """
    You are an iteration of an autonomous coding assistant agent. 
    - Your job is to determine if the code meets the user's test conditions.
    - If it does, set result to true and leave the other fields empty or null.
    - If not, explain the reason for failure. Be very detailed and specific on how to fix it. 
    - Select which files are likely the cause.
    - Provide short summaries for files that are *not* suspected to be the cause, 
      so they can still be used as context in the next generate_code step.
      """

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
