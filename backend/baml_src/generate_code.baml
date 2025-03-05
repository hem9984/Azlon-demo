// ./backend/baml_src/generate_code.baml

//maybe tell it to only generate Dockerfile if there is something wrong with the current one. AND EXPERIMENT WITH GIT MERGE ONLY
// ADD MORE TEST EXAMPLES HERE
// preflight directory tree and current directory tree both included in context window

// in the readme it creates, it should describe the differences between the current and the new code, and why the new code is better
// also make it provide snippets only of files that need to be changed

class GenerateCodeInput {
  memories MemoryItem[]? @description("All memories from previous iterations of the codebase.")
  userPrompt string @description("The user's coding request")
  dirTree string? @description("Directory structure included for context.")
  preflightResult PreFlightOutput? @description("Output from a previous preflight step")
  testConditions string @description("Test conditions the code must meet")
  // all changes made in validate_output are passed through here
  validationResult ValidateCodeOutput @description("Result from validator agent")
}

class GenerateCodeOutput {
  dockerfile string @description(#"
    Docker configuration for running the code.
    Use triple quotes to denote strings and prevent escape characters:
    """
    [Code]
    """
  "#)
  files FileItem[] @description("List of files to generate or update")
}

template_string PrintPreFlight(pre: PreFlightOutput?) #"
    {% if pre %}
    Directory tree:
    {{ pre.dirTree }}

    Run output:
    {{ pre.runOutput }}
    {% endif %}
"#

function GenerateCode(input: GenerateCodeInput, systemprompt: string?, memories: MemoryItem[]?) -> GenerateCodeOutput {
  client Gpt4o_0temp
  prompt #"
    {% if systemprompt!=null %}
    {{ systemprompt }}
    {% else %}
    You are an autonomous coding agent. Your goal is to generate or modify code files so that:
    - The user's prompt requirements are met
    - The code meets the given test conditions
    - The Dockerfile is prepared to run the code automatically
    - Create as many files as necessary to fulfill the user's request.

    Guidelines:
    - Include a readme.md that includes a guide on how to run the code and a summary of how the code works.
    - If a Dockerfile does not already exist, or no specific instructions are provided, use 'python:3.10-slim' as the base image.
    - Install necessary dependencies in the Dockerfile.
    - Ensure multiple commands or scripts can be run from the Dockerfile if needed.
    - All program output should appear on stdout without additional intervention.
    - Include any libraries or drivers needed for the code to run properly.
    - Use ENTRYPOINT in the Dockerfile so the container runs automatically.
    - The final code must pass the test conditions.
    {% endif %}

    {{ ctx.output_format(prefix = "answer with this schema: \n") }}

    {{ _.role("user") }}
    # Memories from previous attempts:
    {{ input.memories }}

    # User Request:
    {{ input.userPrompt }}

    # Test Conditions:
    {{ input.testConditions }}

    # Current State of the Codebase:
    Directory Tree: 
    {{ input.dirTree }}

    # Preflight Info:
    {{ PrintPreFlight(input.preflightResult) }}

    {% if input.validationResult is not none and input.validationResult.reason %}
    # Previous Validation Results:
    Failure Reason: {{ input.validationResult.reason }}
    {% endif %}
  "#
}

test GenerateSimpleScript {
  functions [GenerateCode]
  args {
    input {
      userPrompt "Create a hello world script"
      testConditions "Script should print 'Hello, World!' to stdout"
    }
  }
}

test GenerateComplexProject {
  functions [GenerateCode]
  args {
    input {
      userPrompt "Create a Flask API with a single endpoint that returns the current time"
      testConditions "API should respond to GET / with current timestamp in ISO format"
    }
  }
}