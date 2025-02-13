// ./backend/baml_src/schema.baml

class FileItem {
  filename string @description("Name of the file.")
  content string @description("Full content of the file.")
}

class PreFlightOutput {
  dirTree string @description("Directory structure from preflight check")
  runOutput string @description("Output from preflight execution")
}