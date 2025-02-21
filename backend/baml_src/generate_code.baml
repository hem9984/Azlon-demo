// ./backend/baml_src/generate_code.baml

//maybe tell it to only generate Dockerfile if there is something wrong with the current one
// preflight directory tree and current directory tree both included in context window

// in the readme it creates, it should describe the differences between the current and the new code, and why the new code is better
// also make it provide snippets only of files that need to be changed

class GenerateCodeInput {
  userPrompt string @description("The user's coding request")
  dirTree string? @description("Directory structure included for context.")
  preflightResult PreFlightOutput? @description("Output from a previous preflight step")
  testConditions string @description("Test conditions the code must meet")
  validationResult ValidateCodeOutput? @description("Result from previous validation step if this is a retry")
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

function GenerateCode(input: GenerateCodeInput, systemprompt: string?) -> GenerateCodeOutput {
  client Gpt4o_0temp
  prompt #"
    {% if systemprompt!=null %}
    {{ systemprompt }}
    {% else %}
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
    {% endif %}

    {{ ctx.output_format(prefix = "answer with this schema: \n") }}

    {{ _.role("user") }} 
    # User Request:
    {{ input.userPrompt }}

    # Test Conditions:
    {{ input.testConditions }}

    # Current State of the Codebase:
    Directory Tree: 
    {{ input.dirTree }}

    # Preflight Info:
    {{ PrintPreFlight(input.preflightResult) }}

    {% if input.validationResult and not input.validationResult.result %}
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