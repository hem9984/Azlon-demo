// ./backend/baml_src/validate_output.baml

class ValidateCodeInput {
  dockerfile string
  files FileItem[]
  output string
  userPrompt string
  testConditions string
  iteration int
}

class ValidateCodeOutput {
  result bool
  dockerfile string?
  files FileItem[]?
}

function ValidateOutput(input: ValidateCodeInput, systemprompt: string?) -> ValidateCodeOutput {
  client CustomGPT4o
  prompt #"
    {% if systemprompt %}
    {{ systemprompt }}
    {% else %}
    You are an iteration of an autonomous coding assistant agent. 
    If you change any files, provide complete file content replacements. 
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
//     functions [ValidateOutput]
//     args {
//         input {
//             dockerfile "FROM python:3.10-slim"
//             files [
//                 {
//                     filename "main.py"
//                     content '''
// print("Hello World")
// '''
//                     }
//             ]
//             output "Hello World"
//             userPrompt "Create a hello world script"
//             testConditions "Should print Hello World"
//             iteration 1
//         }
//     }
// }
