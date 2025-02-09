// ./backend/baml_src/generate_code.baml

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
  dirTree string? @description("Directory structure included for context.") 
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
    You are an autonomous coding agent. If you need to create new files, provide complete code. Otherwise, generate replacement code snippets. Assume a git merge of your snippet with the current state of the codebase will be applied.

    Given the following requirements:
    - Start with a readme.md containing a summary and step-by-step plan
    - If a Dockerfile does not already exist or specific instructions are not provided, use python:3.10-slim as base Docker image
    - Install necessary dependencies in Dockerfile
    - Run multiple commands using CMD in the Dockerfile to set up the environment if needed
    - Output must be visible on stdout without intervention
    - Run multiple Python files in the Dockerfile using CDM if needed
    - Follow the commands in the readme.md or user_prompt to ensure the code runs correctly
    - Install any drivers or libraries required for the code to run in the Dockerfile
    - Dockerfile should define ENTRYPOINT to run automatically
    - Output must be visible on stdout without intervention
    - Files should be ordered: readme.md, config files, main application files
    {% endif %}

    {{ ctx.output_format }}

    {{ _.role("user") }} User Request:
    {{ input.userPrompt }}

    Test Conditions:
    {{ input.testConditions }}
    Here is the current state of the codebase you will apply your changes to:
    Directory Tree: 
    {{ input.dirTree }}
    Code files:
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

test GenerateSimpleScriptWithPreflight {
  functions [GenerateCode]
  args {
    input {
      userPrompt "Create a hello world script"
      testConditions "Script should print 'Hello, World!' to stdout"
      preflight_result {
        dir_tree "main.py"
        run_output "Hello, World!"
      }
    }
  }
}

test Linearregression {
  functions [GenerateCode]
  args {
    input {
      userPrompt "write a python script that performs linear regression on a csv file. create another file that generates the synthetic csv file to use on the first script"
      testConditions "no errors in output"
    }
  }
}