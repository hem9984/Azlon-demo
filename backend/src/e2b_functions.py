# ./backend/src/e2b_functions.py

import io
import os
from typing import Any, Dict, List, Optional

from e2b import Sandbox
from restack_ai.utils import log

from src.file_server import (
    create_bucket_if_not_exists,
    download_file,
    generate_directory_tree,
    list_files,
    upload_file,
)


class E2BFunctions:
    def __init__(self) -> None:
        # This template allows us to build and run docker containers inside E2B sandbox
        self.template = "e2b-with-docker"
        self.api_key = os.environ.get("E2B_API_KEY")
        # We'll create a new sandbox for each run

    async def run_docker_container(
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
            await self._upload_files_to_e2b(sbx, bucket_name, files)

            # Check if Dockerfile exists
            dockerfile_exists = await self._file_exists_in_e2b(sbx, "/app/Dockerfile")
            if not dockerfile_exists:
                log.warning(f"No Dockerfile found for {prefix}")
                sbx.kill()
                return {
                    "output": "No Dockerfile found in the uploaded files",
                    "status": "error",
                    "modified_files": [],
                }

            # Run ls command to see the files
            ls_result = await sbx.commands.run("ls -la /app")
            log.info(f"Files in E2B sandbox: {ls_result.stdout}")

            # Build Docker container
            log.info("Building Docker container in E2B sandbox")
            build_result = await sbx.commands.run("cd /app && docker build -t app-container .")

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
            run_result = await sbx.commands.run("cd /app && docker run --rm app-container")

            # Get the list of files after container execution
            post_run_files = await self._list_files_in_e2b(sbx, "/app")

            # Find modified or new files
            modified_files = []
            for file_path in post_run_files:
                # Skip common files that shouldn't be considered
                if any(file_path.endswith(ext) for ext in [".git", "__pycache__", ".pyc"]):
                    continue

                # Download the file from E2B
                content = await self._download_file_from_e2b(sbx, file_path)
                if content:
                    # Generate relative path for S3
                    rel_path = file_path.replace("/app/", "")
                    s3_key = f"{prefix}{rel_path}"

                    # Upload the file to MinIO
                    upload_file(io.BytesIO(content), bucket_name, s3_key)
                    modified_files.append(rel_path)

            # Generate directory tree
            tree = generate_directory_tree(bucket_name, prefix)

            # Close the sandbox
            sbx.kill()

            return {
                "output": run_result.stdout if run_result.exit_code == 0 else run_result.stderr,
                "status": "success" if run_result.exit_code == 0 else "error",
                "modified_files": modified_files,
                "directory_tree": tree,
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

    async def _upload_files_to_e2b(
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
        await sbx.commands.run("mkdir -p /app")

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
                await sbx.commands.run(f"mkdir -p {dir_path}")

            # Upload file to E2B
            await sbx.files.write(e2b_path, content)
            log.debug(f"Uploaded {key} to E2B at {e2b_path}")

    async def _list_files_in_e2b(self, sbx: Sandbox, directory: str) -> List[str]:
        """
        List all files in an E2B directory recursively

        Args:
            sbx: E2B Sandbox instance
            directory: Directory path in E2B

        Returns:
            List[str]: List of file paths
        """
        result = await sbx.commands.run(f"find {directory} -type f | sort")
        if result.exit_code != 0:
            log.error(f"Failed to list files in E2B: {result.stderr}")
            return []

        files = result.stdout.strip().split("\n")
        return [f for f in files if f]  # Filter out empty lines

    async def _download_file_from_e2b(self, sbx: Sandbox, file_path: str) -> Optional[bytes]:
        """
        Download a file from E2B

        Args:
            sbx: E2B Sandbox instance
            file_path: Path to file in E2B

        Returns:
            Optional[bytes]: File content or None if failed
        """
        try:
            content = await sbx.files.read(file_path)
            return content
        except Exception as e:
            log.error(f"Failed to download file {file_path} from E2B: {e}")
            return None

    async def _file_exists_in_e2b(self, sbx: Sandbox, file_path: str) -> bool:
        """
        Check if a file exists in E2B

        Args:
            sbx: E2B Sandbox instance
            file_path: Path to file in E2B

        Returns:
            bool: True if file exists, False otherwise
        """
        result = await sbx.commands.run(
            f"test -f {file_path} && echo 'exists' || echo 'not exists'"
        )
        return result.stdout.strip() == "exists"

    async def generate_directory_tree(self, sbx: Sandbox, directory: str) -> str:
        """
        Generate a tree-like representation of files in an E2B directory

        Args:
            sbx: E2B Sandbox instance
            directory: Directory path in E2B

        Returns:
            str: Tree-like representation of files
        """
        try:
            result = await sbx.commands.run(f"find {directory} -type f | sort")
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
