// ./backend/baml_src/validate_output.baml

//sometimes includes csv file as suspected file which can cause token overload
//since temperature is low, it is not very creative and often oscillates back and forth between a couple errors
// rarely adds more files in later iterations. the first iteration usually determines the files, and all subsequent iterations just work with those files

// experiment with giving validate output high temp, and generate code low temp

// prompt: in your description, tell it to create new files if needed or change its approach. be detailed and thorough in your inscructions for creating the code

class DirectlySuspectedFile {
  filename string @description("Relative path/filename for the code file")
  @@dynamic // This is a dynamic field that can be used to provide full content of the file
}

class UnsuspectedFile {
  filename string @description("Relative path/filename for the code file")
  content string @description(#"
    Summary of the file's contents to give context to the LLM.
    Provide only as much detail as needed for generate_code to understand.
  "#)
}

class ValidateCodeInput {
  memories MemoryItem[]? @description("All memories from previous iterations of the codebase.")
  dirTree string? @description("Directory structure included for context.")
  dockerfile string @description("The Dockerfile from the current code state or newly generated snippet.")
  files FileItem[] @description("All code files from the current iteration of the codebase.")
  output string @description("The container's stdout or stderr from the last run.")
  userPrompt string @description("The user's original coding request/instructions.")
  testConditions string @description("The conditions the code must meet (e.g. 'no errors in output').")
  iteration int @description("Zero-based or 1-based iteration count of the workflow cycle.")
}

class ValidateCodeOutput {
  result bool @description(#"
    Whether the code meets all test conditions and there is absolutely no error in the output. 
    If result is true, return null (or empty arrays) for the other fields.
    If false, fill in the rest of the fields.
  "#)
  
  reason string? @description(#"
  If result is false, the reason or suspected cause for the failure, plus any insights on how to fix it.
  Think about a detailed explanation that would help a developer understand and correct the issue.
  Think about the most likely reasons for the failure and provide a clear path to resolution.
  Think about a solution that minimizes the possibility of breaking other parts of the codebase.
  "#)

  plan string? @description(#"
  A new high-level plan of how to accomplish the goal. 
  This should be a framework of the strategy to achieve the goal, and implementation steps.
  "#)

  suspectedFiles DirectlySuspectedFile[] @description(#"
  Files to be included in their entirety for the next iteration of generate_code.
  Do not include data files such as CSVs. If the code is not using the CSV file properly, explain that in the reason field.
  "#)
  unsuspectedFiles UnsuspectedFile[] @description("Files not suspected to have caused the error; only a summary of their content is needed.")
}

function ValidateOutput(input: ValidateCodeInput, systemprompt: string?, memories: MemoryItem[]?) -> ValidateCodeOutput {
  client Gpt4o_3temp
  prompt #"
    {% if systemprompt!=null %}
    {{ systemprompt }}
    {% else %}
    You are an iteration of an autonomous coding assistant agent. 
    - Your job is to determine if the code meets the user's test conditions.
    - If it does, set result to true and leave the other fields empty or null.
    - If not, explain the reason for failure. Be very detailed and specific on how to fix it. 
    - Select which files are likely the cause.
    - Provide short summaries for files that are *not* suspected to be the cause, 
      so they can still be used as context in the next generate_code step.

    You are also the orchestrator and decision maker of the workflow. Create a new plan or refine the existing one to maximize the success of the code generation phase.
    {% endif %}

    {{ ctx.output_format }}

    {{ _.role("user") }} 
    Memories from previous attempts:
    {{ input.memories }}
    
    The test conditions: 
    {{ input.testConditions }}

    The initial user request:
    {{ input.userPrompt }}

    Directory Tree (for context):
    {{ input.dirTree }}

    Dockerfile (for current iteration):
    {{ input.dockerfile }}

    Code Files:
    {% for file in input.files %}
    #./{{ file.filename }}
    {{ file.content }}
    {% endfor %}

    Container Output:
    {{ input.output }}

    {% if input.iteration > 5 %}
    Since we have been trying for a while, be less strict in what you consider a True result. Just that there are no errors is usually good enough.
    {% endif %}
  "#
}

test ValidateSimpleScript {
  functions [ValidateOutput]
  args {
    input {
      dockerfile "FROM python:3.10-slim"
      files [
        {
          filename "main.py"
          content #"
          print('Hello World')
          "#
        },
      ]
      output "Hello World"
      userPrompt "Create a hello world script"
      testConditions "Should print Hello World"
      iteration 1
    }
  }
}

test NoDockerfilePreflight {
  functions [ValidateOutput]
  args {
    input {
      dirTree "/app/output/workspace_20250212_150959\n└── embeddings.csv\n\n1 directory, 1 file\n"
      dockerfile "No Dockerfile yet"
      files [
        {
          filename "embeddings.csv"
          content "\"manu_name\",\"image_name\",\"base64_encoding\",\"image_vector\",\"filename_vector\",\"id\"\n\"Huizhou Suan Technology Co., Ltd.\",\"500 ml Digital Thermos Cup Intelligent  Temperature Display Water Bottle Heat Preservation Vacuum Thermos Flask For Coffee Tea\",\"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh... (truncated special ext)"
        }
      ]
      iteration 1
      output "No Dockerfile found. Preflight was skipped."
      testConditions "no errors in output"
      userPrompt "create a flask server that does cosine similarity with numpy on a user input vector with all the vectors in the embedding column of the provided CSV"
    }
  }
}

test ChangeOfPlan {
  functions [ValidateOutput]
  args {
    input {
      dirTree "/app/output/workspace_20250212_150959\n└── embeddings.csv\n\n1 directory, 1 file\n"
      dockerfile "No Dockerfile yet"
      files [
        {
          filename "embeddings.csv"
          content "\"manu_name\",\"image_name\",\"base64_encoding\",\"image_vector\",\"filename_vector\",\"id\"\n\"Huizhou Suan Technology Co., Ltd.\",\"500 ml Digital Thermos Cup Intelligent  Temperature Display Water Bottle Heat Preservation Vacuum Thermos Flask For Coffee Tea\",\"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh... (truncated special ext)"
        }
      ]
      iteration 4
      output "Error: Pytorch no longer supports this functionality, use Tensorflow instead."
      testConditions "no errors in output"
      userPrompt "create a flask server that does cosine similarity with numpy on a user input vector with all the vectors in the embedding column of the provided CSV"
    }
  }
}