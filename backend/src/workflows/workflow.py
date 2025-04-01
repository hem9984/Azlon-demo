# ./backend/src/workflows/workflow.py
from restack_ai.workflow import workflow, import_functions, log
from dataclasses import dataclass
from datetime import timedelta
from datetime import datetime
import re
from typing import List, Dict, Tuple

with import_functions():
    from src.functions.functions import generate_code, run_locally, validate_output
    from src.functions.functions import GenerateCodeInput, RunCodeInput, ValidateOutputInput

@dataclass
class WorkflowInputParams:
    user_prompt: str
    test_conditions: str

class SecurityValidator:
    """
    Validates generated code for security issues before execution.
    """
    # Dockerfile security patterns to check
    DOCKERFILE_PATTERNS = [
        # Container escape attempts
        (r'--privileged', "Privileged mode is not allowed"),
        (r'--cap-add', "Adding capabilities is not allowed"),
        (r'--device', "Direct device access is not allowed"),
        (r'/dev/', "Direct access to /dev is not allowed"),
        (r'/proc/', "Direct access to /proc is not allowed"),
        (r'/sys/', "Direct access to /sys is not allowed"),
        # Network concerns
        (r'--net=host', "Host network mode is not allowed"),
        (r'--network=host', "Host network mode is not allowed"),
        # Volume mounting concerns
        (r'-v\s+/:', "Mounting host root is not allowed"),
        (r'--volume\s+/:', "Mounting host root is not allowed"),
        # Executing remote code
        (r'curl\s+.*\s+\|\s+(?:bash|sh)', "Pipe to shell from curl is not allowed"),
        (r'wget\s+.*\s+\|\s+(?:bash|sh)', "Pipe to shell from wget is not allowed"),
        # General suspiciousness
        (r'rm\s+-rf\s+/', "Deleting root directory is not allowed")
    ]
    
    # File content security patterns by file extension
    FILE_PATTERNS = {
        # Python-specific patterns
        '.py': [
            (r'subprocess\.(?:call|Popen|run)', "Arbitrary subprocess execution is not allowed"),
            (r'os\.system', "Arbitrary system command execution is not allowed"),
            (r'exec\s*\(', "Dynamic code execution is not allowed"),
            (r'eval\s*\(', "Dynamic code evaluation is not allowed"),
            (r'__import__\(', "Dynamic imports are restricted"),
            (r'importlib', "Dynamic importing is restricted"),
        ],
        # Shell script patterns
        '.sh': [
            (r'rm\s+-rf\s+/', "Deleting root directory is not allowed"),
            (r'curl\s+.*\s+\|\s+(?:bash|sh)', "Pipe to shell is not allowed"),
            (r'wget\s+.*\s+\|\s+(?:bash|sh)', "Pipe to shell is not allowed"),
        ],
        # JavaScript patterns
        '.js': [
            (r'eval\s*\(', "Dynamic code evaluation is not allowed"),
            (r'new\s+Function\s*\(', "Dynamic code execution is not allowed"),
            (r'child_process', "Process execution is not allowed"),
        ],
        # General patterns for all file types
        '*': [
            (r'(?:bash|sh|zsh)\s+-c', "Shell execution is restricted"),
        ]
    }
    
    @classmethod
    def validate_dockerfile(cls, dockerfile: str) -> Tuple[bool, List[str]]:
        """
        Validates Dockerfile content for security issues.
        
        Args:
            dockerfile: String content of the Dockerfile
            
        Returns:
            Tuple of (is_safe, list_of_issues)
        """
        issues = []
        
        for pattern, message in cls.DOCKERFILE_PATTERNS:
            if re.search(pattern, dockerfile, re.IGNORECASE):
                issues.append(message)
        
        return len(issues) == 0, issues
    
    @classmethod
    def validate_file(cls, content: str, filename: str) -> Tuple[bool, List[str]]:
        """
        Validates file content for security issues.
        
        Args:
            content: String content of the file
            filename: Name of the file (used to determine file type)
            
        Returns:
            Tuple of (is_safe, list_of_issues)
        """
        issues = []
        ext = '.' + filename.split('.')[-1] if '.' in filename else ''
        
        # Apply patterns for this file extension
        if ext in cls.FILE_PATTERNS:
            for pattern, message in cls.FILE_PATTERNS[ext]:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(f"{message} in {filename}")
        
        # Apply general patterns for all files
        for pattern, message in cls.FILE_PATTERNS.get('*', []):
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"{message} in {filename}")
        
        return len(issues) == 0, issues
    
    @classmethod
    def validate_files(cls, files: List[Dict[str, str]]) -> Tuple[bool, List[str]]:
        """
        Validates multiple files for security issues.
        
        Args:
            files: List of dictionaries with 'filename' and 'content' keys
            
        Returns:
            Tuple of (is_safe, list_of_issues)
        """
        all_issues = []
        for file_data in files:
            filename = file_data.get('filename', '')
            content = file_data.get('content', '')
            is_safe, issues = cls.validate_file(content, filename)
            all_issues.extend(issues)
        
        return len(all_issues) == 0, all_issues

@workflow.defn()
class AutonomousCodingWorkflow:
    @workflow.run
    async def run(self, input: WorkflowInputParams):
        log.info("AutonomousCodingWorkflow started", input=input)

        gen_output = await workflow.step(
            generate_code,
            GenerateCodeInput(
                user_prompt=input.user_prompt,
                test_conditions=input.test_conditions
            ),
            start_to_close_timeout=timedelta(seconds=300)
        )

        dockerfile = gen_output.dockerfile
        files = gen_output.files  # list of {"filename":..., "content":...}

        iteration_count = 0
        max_iterations = 20

        while iteration_count < max_iterations:
            iteration_count += 1
            log.info(f"Iteration {iteration_count} start")

            # Security validation before execution
            is_dockerfile_safe, dockerfile_issues = SecurityValidator.validate_dockerfile(dockerfile)
            if not is_dockerfile_safe:
                log.error("Security issues detected in Dockerfile", issues=dockerfile_issues)
                return False
            
            is_files_safe, files_issues = SecurityValidator.validate_files(files)
            if not is_files_safe:
                log.error("Security issues detected in generated files", issues=files_issues)
                return False

            run_output = await workflow.step(
                run_locally,
                RunCodeInput(dockerfile=dockerfile, files=files),
                start_to_close_timeout=timedelta(seconds=300)
            )

            val_output = await workflow.step(
                validate_output,
                ValidateOutputInput(
                    dockerfile=dockerfile,
                    files=files,
                    output=run_output.output,
                    test_conditions=input.test_conditions
                ),
                start_to_close_timeout=timedelta(seconds=300)
            )

            if val_output.result:
                log.info("AutonomousCodingWorkflow completed successfully")
                return True
            else:
                changed_files = val_output.files if val_output.files else []
                
                # Validate and update dockerfile if changed
                if val_output.dockerfile:
                    is_new_dockerfile_safe, new_dockerfile_issues = SecurityValidator.validate_dockerfile(
                        val_output.dockerfile
                    )
                    if not is_new_dockerfile_safe:
                        log.error("Security issues detected in updated Dockerfile", 
                                 issues=new_dockerfile_issues)
                        return False
                    dockerfile = val_output.dockerfile

                # Validate and update files if changed
                if changed_files:
                    is_changed_files_safe, changed_files_issues = SecurityValidator.validate_files(changed_files)
                    if not is_changed_files_safe:
                        log.error("Security issues detected in updated files", 
                                 issues=changed_files_issues)
                        return False
                    
                    # Update the files list in-memory
                    for changed_file in changed_files:
                        changed_filename = changed_file["filename"]
                        changed_content = changed_file["content"]
                        
                        found = False
                        for i, existing_file in enumerate(files):
                            if existing_file["filename"] == changed_filename:
                                files[i]["content"] = changed_content
                                found = True
                                break
                        if not found:
                            files.append({"filename": changed_filename, "content": changed_content})

        log.warn("AutonomousCodingWorkflow reached max iterations without success")
        return False