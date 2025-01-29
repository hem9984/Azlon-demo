class FileItem {
  filename string @description("Name of the file to generate")
  content string @description(#"
    Content of the file
    Use triplequote strings to prevent escape characters
    '''
    [Code]
    '''
  "#)
}

class GenerateCodeInput {
  /// The user's coding request
  userPrompt string
  /// The result of the preflight check
  preflight_result PreFlightOutput? 
  /// Test conditions the code must meet
  testConditions string
}

class GenerateCodeOutput {
  dockerfile string @description(#"
    Docker configuration for running the code
    Use triplequote strings to prevent escape characters
    '''
    [Code]
    '''
  "#)
  files FileItem[] @description("List of files to generate")
}


class PreFlightOutput {
    dir_tree string
    run_output string
}


template_string PrintPreFlight(pre: PreFlightOutput?) #"
    {% if pre %}
    Directory tree:
    {{ pre.dir_tree }}
    Run output:
    {{ pre.run_output }}
    {% endif %}
"#

function GenerateCode(input: GenerateCodeInput, systemprompt: string?) -> GenerateCodeOutput {
  client CustomGPT4o
  prompt #"
    {% if systemprompt %}
    {{ systemprompt }}
    {% else %}
    You are an autonomous coding agent. Generate complete code that will run.

    Given the following requirements:
    - Start with a readme.md containing a summary and step-by-step plan
    - Use python:3.10-slim as base Docker image
    - Install necessary dependencies in Dockerfile
    - Each file should start with #./<filename>
    - Dockerfile should define ENTRYPOINT to run automatically
    - Output must be visible on stdout without intervention
    - Files should be ordered: readme.md, config files, main application files
    {% endif %}

    {{ ctx.output_format }}

    {{ _.role("user") }} User Request:
    {{ input.userPrompt }}

    Test Conditions:
    {{ input.testConditions }}

    {{ PrintPreFlight(input.preflight_result) }}
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

test tacos {
  functions [GenerateCode]
  args {
    input {
      userPrompt "instead of code, lets talk about chess"
      testConditions "who is the best player of all time?"
    }
  }
}