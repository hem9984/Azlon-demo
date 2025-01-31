// ./backend/baml_src/validate_output.baml

/// A file item representing a single code file to merge
// class FileItem {
//   filename string @description("Relative path/filename for the code file")
//   content string @description(#"
//     The code or text content of this file.
//     Use triplequote strings to prevent escape characters
//     '''
//     [Code snippet]
//     '''
//   "#)
// }

/// Inputs for ValidateOutput
class ValidateCodeInput {
  dockerfile string @description("The Dockerfile from the current code state or newly generated snippet.")
  files FileItem[] @description("All code files from the current iteration of the codebase.")
  output string @description("The container's stdout or stderr from the last run.")
  userPrompt string @description("The user's original coding request/instructions.")
  testConditions string @description("The conditions the code must meet (e.g. 'no errors in output').")
  iteration int @description("Zero-based or 1-based iteration count of the workflow cycle.")
}

/// Outputs from ValidateOutput
class ValidateCodeOutput {
  result bool @description("Whether the code meets all test conditions.")
  dockerfile string? @description(#"
    A new or updated Dockerfile if changes are necessary. 
    Use triplequote strings if needed for clarity.
    '''
    [Code]
    '''
  "#)
  files FileItem[]? @description("A list of new or updated code files if changes are required. Use triplequote strings for code content.")
}

/// The ValidateOutput function calls your GPT-like model 
/// to check if the code meets test conditions and possibly 
/// return updated file snippets or Dockerfile changes
function ValidateOutput(input: ValidateCodeInput, systemprompt: string?) -> ValidateCodeOutput {
  client Llama3
  //client CustomGPT4o
  prompt #"
    {% if systemprompt %}
    {{ systemprompt }}
    {% else %}
    You are an iteration of an autonomous coding assistant agent. 
    If you change any files, provide code snippet replacements to be used in a git merge. 
    Append a brief explanation at the bottom of readme.md about what you tried.

    Please validate if the code meets all test conditions and provide any necessary fixes.
    {% endif %}

    {{ ctx.output_format }}

    {{ _.role("user") }} The test conditions: 
    {{ input.testConditions }}

    The initial user request:
    {{ input.userPrompt }}

    Dockerfile:
    {{ input.dockerfile }}

    Files:
    {% for file in input.files %}
    #./{{ file.filename }}
    {{ file.content }}
    {% endfor %}

    Output:
    {{ input.output }}
  "#
}

// test ValidateSimpleScript {
//   functions [ValidateOutput]
//   args {
//     input {
//       dockerfile "FROM python:3.10-slim"
//       files [
//         {
//           filename "main.py"
//           content '''
// print("Hello World")
// '''
//         }
//       ]
//       output "Hello World"
//       userPrompt "Create a hello world script"
//       testConditions "Should print Hello World"
//       iteration 1
//     }
//   }
// }
