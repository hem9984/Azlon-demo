# ./backend/src/e2b_functions.py

import io
import logging
import os
from typing import Any, Dict, List, Optional

from e2b import Sandbox

log = logging.getLogger(__name__)

from src.file_server import (
    create_bucket_if_not_exists,
    download_file,
    generate_directory_tree,
    list_files,
    upload_file,
)


class E2BRunner:
    def __init__(self) -> None:
        # This template allows us to build and run docker containers inside E2B sandbox
        self.template = "e2b-with-docker"
        self.api_key = os.environ.get("E2B_API_KEY")
        # We'll create a new sandbox for each run

    def init_sandbox(self) -> Sandbox:
        """
        Initialize a new E2B sandbox

        Returns:
            Sandbox: E2B Sandbox instance
        """
        sandbox = Sandbox(template=self.template, api_key=self.api_key)
        return sandbox

    def install_packages(self, sandbox: Sandbox, packages: List[str]) -> bool:
        """
        Install Python packages in the sandbox

        Args:
            sandbox: E2B Sandbox instance
            packages: List of package names to install

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            package_str = " ".join(packages)
            result = sandbox.commands.run(f"pip install {package_str}")
            return result.exit_code == 0
        except Exception as e:
            log.error(f"Failed to install packages {packages}: {e}")
            return False

    def upload_file_to_e2b(self, sandbox: Sandbox, content: bytes, file_path: str) -> bool:
        """
        Upload a file to the E2B sandbox

        Args:
            sandbox: E2B Sandbox instance
            content: File content as bytes
            file_path: Target file path in E2B

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            sandbox.files.write(file_path, content)
            return True
        except Exception as e:
            log.error(f"Failed to upload file to {file_path}: {e}")
            return False

    def run_docker_container(
        self, user_id: str, run_id: str, bucket_name: str = "azlon-files"
    ) -> Dict[str, Any]:
        """
        Main function to handle the entire process:
        1. Create E2B sandbox
        2. Download files from MinIO
        3. Build and run Docker container
        4. Upload modified files back to MinIO
        5. Clean up and return results

        Args:
            user_id: User ID
            run_id: Run ID
            bucket_name: MinIO bucket name

        Returns:
            Dict: Result with output, status, and modified files
        """
        # Create a fresh sandbox for this run
        sbx = Sandbox(template=self.template, api_key=self.api_key)
        try:
            log.info(f"Created E2B sandbox for user {user_id}, run {run_id}")

            # Ensure bucket exists
            create_bucket_if_not_exists(bucket_name)

            # Prefix for files in MinIO
            prefix = f"{user_id}/{run_id}/"

            # Get the list of files from MinIO
            files = list_files(bucket_name, prefix)
            if not files:
                log.warning(f"No files found for {prefix} in bucket {bucket_name}")
                sbx.kill()
                return {
                    "output": "No files found for the specified user and run ID",
                    "status": "error",
                    "modified_files": [],
                }

            # Download files from MinIO and upload to E2B
            self._upload_files_to_e2b(sbx, bucket_name, files)

            # Check if Dockerfile exists
            dockerfile_exists = self._file_exists_in_e2b(sbx, "/app/Dockerfile")
            if not dockerfile_exists:
                log.warning(f"No Dockerfile found for {prefix}")
                sbx.kill()
                return {
                    "output": "No Dockerfile found in the uploaded files",
                    "status": "error",
                    "modified_files": [],
                }

            # Run ls command to see the files
            ls_result = sbx.commands.run("ls -la /app")
            log.info(f"Files in E2B sandbox: {ls_result.stdout}")

            # Build Docker container
            log.info("Building Docker container in E2B sandbox")
            build_result = sbx.commands.run("cd /app && docker build -t app-container .")

            if build_result.exit_code != 0:
                log.error(f"Docker build failed: {build_result.stderr}")
                sbx.kill()
                return {
                    "output": f"Docker build failed:\n{build_result.stderr}",
                    "status": "error",
                    "modified_files": [],
                }

            # Run Docker container
            log.info("Running Docker container in E2B sandbox")
            run_result = sbx.commands.run("cd /app && docker run --rm app-container")

            # Get the list of files after container execution
            post_run_files = self._list_files_in_e2b(sbx, "/app")

            # Find modified or new files
            modified_files = []
            for file_path in post_run_files:
                # Skip common files that shouldn't be considered
                if any(file_path.endswith(ext) for ext in [".git", "__pycache__", ".pyc"]):
                    continue

                # Download the file from E2B
                content = self._download_file_from_e2b(sbx, file_path)
                if content:
                    # Generate relative path for S3
                    rel_path = file_path.replace("/app/", "")
                    s3_key = f"{prefix}{rel_path}"

                    # Upload the file to MinIO
                    upload_file(io.BytesIO(content), bucket_name, s3_key)
                    modified_files.append(rel_path)

            # Generate directory tree
            directory_tree = generate_directory_tree(bucket_name, prefix)

            # Close the sandbox
            sbx.kill()

            return {
                "output": run_result.stdout if run_result.exit_code == 0 else run_result.stderr,
                "status": "success" if run_result.exit_code == 0 else "error",
                "modified_files": modified_files,
                "directory_tree": directory_tree,
            }

        except Exception as e:
            log.error(f"Error in E2B execution: {str(e)}")
            try:
                sbx.kill()
            except:
                pass
            return {
                "output": f"Error during execution: {str(e)}",
                "status": "error",
                "modified_files": [],
            }

    def _upload_files_to_e2b(
        self, sbx: Sandbox, bucket_name: str, files: List[Dict[str, Any]]
    ) -> None:
        """
        Download files from MinIO and upload them to E2B

        Args:
            sbx: E2B Sandbox instance
            bucket_name: MinIO bucket name
            files: List of files from MinIO
        """
        # Create /app directory in E2B
        sbx.commands.run("mkdir -p /app")

        for file_info in files:
            key = file_info["key"]

            # Download file from MinIO
            content = download_file(bucket_name, key)
            if not content or not isinstance(content, bytes):
                log.warning(f"Failed to download file {key} from MinIO")
                continue

            # Determine the path in E2B
            # Extract the path after user_id/run_id/
            path_parts = key.split("/", 2)
            if len(path_parts) < 3:
                continue

            relative_path = path_parts[2]
            e2b_path = f"/app/{relative_path}"

            # Create directories if necessary
            dir_path = os.path.dirname(e2b_path)
            if dir_path != "/app":
                sbx.commands.run(f"mkdir -p {dir_path}")

            # Upload file to E2B
            sbx.files.write(e2b_path, content)
            log.debug(f"Uploaded {key} to E2B at {e2b_path}")

    def _list_files_in_e2b(self, sbx: Sandbox, directory: str) -> List[str]:
        """
        List all files in an E2B directory recursively

        Args:
            sbx: E2B Sandbox instance
            directory: Directory path in E2B

        Returns:
            List[str]: List of file paths
        """
        result = sbx.commands.run(f"find {directory} -type f | sort")
        if result.exit_code != 0:
            log.error(f"Failed to list files in E2B: {result.stderr}")
            return []

        files = result.stdout.strip().split("\n")
        return [f for f in files if f]  # Filter out empty lines

    def _download_file_from_e2b(self, sbx: Sandbox, file_path: str) -> Optional[bytes]:
        """
        Download a file from E2B

        Args:
            sbx: E2B Sandbox instance
            file_path: Path to file in E2B

        Returns:
            Optional[bytes]: File content or None if failed
        """
        try:
            content = sbx.files.read(file_path)
            # Convert string to bytes if needed
            if isinstance(content, str):
                return content.encode("utf-8")
            return content
        except Exception as e:
            log.error(f"Failed to download file {file_path} from E2B: {e}")
            return None

    def download_file_from_e2b(self, sandbox: Sandbox, file_path: str) -> Optional[bytes]:
        """
        Download a file from E2B

        Args:
            sandbox: E2B Sandbox instance
            file_path: Path to file in E2B

        Returns:
            Optional[bytes]: File content or None if failed
        """
        try:
            content = sandbox.files.read(file_path)
            # Convert string to bytes if needed
            if isinstance(content, str):
                return content.encode("utf-8")
            return content
        except Exception as e:
            log.error(f"Failed to download file {file_path} from E2B: {e}")
            return None

    def _file_exists_in_e2b(self, sbx: Sandbox, file_path: str) -> bool:
        """
        Check if a file exists in E2B

        Args:
            sbx: E2B Sandbox instance
            file_path: Path to file in E2B

        Returns:
            bool: True if file exists, False otherwise
        """
        result = sbx.commands.run(f"test -f {file_path} && echo 'exists' || echo 'not exists'")
        return result.stdout.strip() == "exists"

    def file_exists_in_e2b(self, sandbox: Sandbox, file_path: str) -> bool:
        """
        Public method to check if a file exists in E2B

        Args:
            sandbox: E2B Sandbox instance
            file_path: Path to file in E2B

        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            result = self._file_exists_in_e2b(sandbox, file_path)
            return result
        except Exception as e:
            log.error(f"Failed to check if file {file_path} exists in E2B: {e}")
            return False

    def run_command_in_e2b(self, sandbox: Sandbox, command: str) -> Any:
        """
        Run a command in the E2B sandbox

        Args:
            sandbox: E2B Sandbox instance
            command: Command to run

        Returns:
            Any: Command result object with stdout, stderr, and exit_code
        """
        try:
            result = sandbox.commands.run(command)
            return result
        except Exception as e:
            log.error(f"Failed to run command {command} in E2B: {e}")

            # Create a simple result object with the expected properties
            class ErrorResult:
                def __init__(self):
                    self.stdout = ""
                    self.stderr = f"Error: {str(e)}"
                    self.exit_code = 1

            return ErrorResult()

    def generate_directory_tree(self, sandbox: Sandbox, directory: str) -> str:
        """
        Generate a tree-like representation of files in an E2B directory

        Args:
            sandbox: E2B Sandbox instance
            directory: Directory path in E2B

        Returns:
            str: Tree-like representation of files
        """
        try:
            # Use the find command to get a list of files and the tree command to format it
            # Install tree if it's not already installed
            sandbox.commands.run("apt-get update && apt-get install -y tree || true")
            result = sandbox.commands.run(f"cd {directory} && tree -a")
            if result.exit_code != 0:
                # Fallback if tree command fails
                result = sandbox.commands.run(f"find {directory} -type f | sort")
                if result.exit_code != 0:
                    return f"Error generating directory tree: {result.stderr}"

                files = result.stdout.strip().split("\n")
                return "\n".join(files)

            return result.stdout
        except Exception as e:
            log.error(f"Failed to generate directory tree for {directory}: {e}")
            return f"Error generating directory tree: {str(e)}"

    def _generate_directory_tree(self, sbx: Sandbox, directory: str) -> str:
        """
        Generate a tree-like representation of files in an E2B directory

        Args:
            sbx: E2B Sandbox instance
            directory: Directory path in E2B

        Returns:
            str: Tree-like representation of files
        """
        try:
            result = sbx.commands.run(f"find {directory} -type f | sort")
            if result.exit_code != 0:
                return f"Error generating directory tree: {result.stderr}"

            files = result.stdout.strip().split("\n")
            files = [f.replace(f"{directory}/", "") for f in files if f]

            if not files:
                return f"{directory}\n└── (empty)"

            # Build tree structure
            tree = {}
            for file_path in files:
                current = tree
                components = file_path.split("/")

                for i, component in enumerate(components):
                    if i == len(components) - 1:  # Leaf node (file)
                        current[component] = None
                    else:  # Directory
                        if component not in current:
                            current[component] = {}
                        current = current[component]

            # Generate the tree as a string
            result = [directory]

            def _add_to_result(node, prefix="", is_last=True):
                items = list(node.items())
                for i, (name, children) in enumerate(items):
                    is_last_item = i == len(items) - 1
                    if is_last:
                        result.append(f"{prefix}└── {name}")
                        new_prefix = prefix + "    "
                    else:
                        result.append(f"{prefix}├── {name}")
                        new_prefix = prefix + "│   "

                    if children is not None:  # Directory
                        _add_to_result(children, new_prefix, is_last_item)

            _add_to_result(tree, "", True)
            return "\n".join(result)
        except Exception as e:
            log.error(f"Error generating directory tree: {e}")
            return f"Error generating directory tree: {str(e)}"
