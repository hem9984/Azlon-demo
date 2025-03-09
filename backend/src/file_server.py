# ./backend/src/file_server.py

# INCLUDE ALL THE S3 API FUNCTIONS THAT USE LOCAL MINIO HERE
import io
import logging
import os
import zipfile
from datetime import datetime
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_minio_client():
    """
    Create and return an S3 client configured to use MinIO
    """
    # Check if we should use external endpoint (for Restack cloud access)
    use_external = os.environ.get("USE_EXTERNAL_MINIO", "false").lower() == "true"

    if use_external:
        # Use the public Tailscale URL for external access
        endpoint_url = os.environ.get(
            "MINIO_EXTERNAL_ENDPOINT", "https://muchnic.tail9dec88.ts.net:8443"
        )
        use_ssl = True  # External endpoint must use SSL
    else:
        # Use internal Docker network for container-to-container communication
        endpoint_url = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        use_ssl = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"

    access_key = os.environ.get("MINIO_ROOT_USER", "AKIAIOSFODNN7EXAMPLE")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    # Make sure we have http:// or https:// prefix
    if not endpoint_url.startswith("http"):
        protocol = "https" if use_ssl else "http"
        endpoint_url = f"{protocol}://{endpoint_url}"

    logger.info(f"Connecting to MinIO at {endpoint_url}")

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        use_ssl=use_ssl,
        verify=False,  # Set to True in production with proper certs
    )

    return s3_client


def create_bucket_if_not_exists(bucket_name: str) -> bool:
    """
    Create a bucket if it doesn't exist

    Args:
        bucket_name: Name of the bucket to create

    Returns:
        bool: True if created or already exists, False if failed
    """
    s3_client = get_minio_client()

    try:
        # Check if bucket exists by listing all buckets
        response = s3_client.list_buckets()
        buckets = response.get("Buckets", [])
        bucket_exists = any(bucket["Name"] == bucket_name for bucket in buckets)

        if bucket_exists:
            logger.info(f"Bucket {bucket_name} already exists")
            return True

        # Bucket doesn't exist, create it
        s3_client.create_bucket(Bucket=bucket_name)
        logger.info(f"Created bucket: {bucket_name}")
        return True
    except ClientError as e:
        logger.error(f"Error creating/checking bucket {bucket_name}: {e}")
        return False


def upload_file(
    file_path: Union[str, BinaryIO, bytes, io.BytesIO],
    bucket_name: str,
    object_name: str,
    metadata: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Upload a file to MinIO/S3

    Args:
        file_path: File path or file-like object with data to upload
        bucket_name: Bucket to upload to
        object_name: S3 object name (key)
        metadata: Optional metadata to attach to the file

    Returns:
        bool: True if file was uploaded, False otherwise
    """
    s3_client = get_minio_client()

    # Ensure bucket exists
    if not create_bucket_if_not_exists(bucket_name):
        return False

    try:
        # Handle different input types
        if isinstance(file_path, str):
            # It's a file path
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False

            extra_args = {}
            if metadata:
                extra_args["Metadata"] = metadata

            s3_client.upload_file(file_path, bucket_name, object_name, ExtraArgs=extra_args)
        else:
            # It's a file-like object, bytes, or BytesIO
            extra_args = {}
            if metadata:
                extra_args["Metadata"] = metadata

            # Convert bytes to BytesIO if needed
            if isinstance(file_path, bytes):
                file_path = io.BytesIO(file_path)

            s3_client.upload_fileobj(file_path, bucket_name, object_name, ExtraArgs=extra_args)

        logger.info(f"Uploaded {object_name} to bucket {bucket_name}")
        return True
    except ClientError as e:
        logger.error(f"Error uploading file {object_name} to bucket {bucket_name}: {e}")
        return False


def download_file(
    bucket_name: str, object_name: str, file_path: Optional[str] = None
) -> Union[bytes, bool]:
    """
    Download a file from MinIO/S3

    Args:
        bucket_name: Bucket to download from
        object_name: S3 object name (key)
        file_path: Optional file path to save to. If None, returns the content as bytes.

    Returns:
        bytes or bool: File content as bytes if file_path is None, otherwise True if successful
    """
    s3_client = get_minio_client()

    try:
        if file_path is None:
            # Return the file contents as bytes
            response = s3_client.get_object(Bucket=bucket_name, Key=object_name)
            file_content = response["Body"].read()
            logger.info(f"Downloaded {object_name} from bucket {bucket_name}")
            return file_content
        else:
            # Save to a file path
            s3_client.download_file(bucket_name, object_name, file_path)
            logger.info(f"Downloaded {object_name} from bucket {bucket_name} to {file_path}")
            return True
    except ClientError as e:
        logger.error(f"Error downloading file {object_name} from bucket {bucket_name}: {e}")
        if file_path is None:
            return b""
        return False


def list_files(bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
    """
    List files in a MinIO/S3 bucket with optional prefix

    Args:
        bucket_name: Bucket to list from
        prefix: Optional prefix to filter objects

    Returns:
        List[Dict]: List of objects with information
    """
    s3_client = get_minio_client()

    try:
        # Ensure bucket exists
        create_bucket_if_not_exists(bucket_name)

        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if "Contents" not in response:
            return []

        objects = []
        for obj in response["Contents"]:
            objects.append(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "modified": obj["LastModified"].isoformat()
                    if hasattr(obj["LastModified"], "isoformat")
                    else str(obj["LastModified"]),
                    "etag": obj.get("ETag", "").strip('"'),
                }
            )

        return objects
    except ClientError as e:
        logger.error(f"Error listing files in bucket {bucket_name} with prefix {prefix}: {e}")
        return []


def delete_file(bucket_name: str, object_name: str) -> bool:
    """
    Delete a file from MinIO/S3

    Args:
        bucket_name: Bucket name
        object_name: S3 object name (key)

    Returns:
        bool: True if file was deleted, False otherwise
    """
    s3_client = get_minio_client()

    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        logger.info(f"Deleted {object_name} from bucket {bucket_name}")
        return True
    except ClientError as e:
        logger.error(f"Error deleting file {object_name} from bucket {bucket_name}: {e}")
        return False


def delete_directory(bucket_name: str, prefix: str) -> bool:
    """
    Delete all files under a prefix (S3 doesn't have directories)

    Args:
        bucket_name: Bucket name
        prefix: Prefix to delete (virtual directory)

    Returns:
        bool: True if all files were deleted, False otherwise
    """
    s3_client = get_minio_client()

    try:
        # Make sure prefix ends with a slash if it's meant to be a directory
        if not prefix.endswith("/"):
            prefix += "/"

        # List objects with the given prefix
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if "Contents" not in response:
            logger.info(f"No files found in {prefix} to delete")
            return True

        # Create the delete objects structure
        delete_objects = {"Objects": [{"Key": obj["Key"]} for obj in response["Contents"]]}

        # Delete the objects
        s3_client.delete_objects(Bucket=bucket_name, Delete=delete_objects)
        logger.info(f"Deleted {len(delete_objects['Objects'])} files from {prefix}")
        return True
    except ClientError as e:
        logger.error(f"Error deleting directory {prefix} from bucket {bucket_name}: {e}")
        return False


def file_exists(bucket_name: str, object_name: str) -> bool:
    """
    Check if a file exists in MinIO/S3

    Args:
        bucket_name: Bucket name
        object_name: S3 object name (key)

    Returns:
        bool: True if file exists, False otherwise
    """
    s3_client = get_minio_client()

    try:
        s3_client.head_object(Bucket=bucket_name, Key=object_name)
        return True
    except ClientError as e:
        # If a 404 error, then the object does not exist
        if e.response.get("Error", {}).get("Code") == "404":
            return False
        # Some other error
        logger.error(f"Error checking if {object_name} exists in bucket {bucket_name}: {e}")
        return False


def generate_directory_tree(bucket_name: str, prefix: str = "") -> str:
    """
    Generate a tree-like representation of files in a bucket with prefix

    Args:
        bucket_name: Bucket name
        prefix: Prefix to filter objects

    Returns:
        str: Tree-like representation of files
    """
    files = list_files(bucket_name, prefix)

    if not files:
        return f"{bucket_name}/{prefix}\n└── (empty)"

    # Build tree structure from paths
    tree = {}
    for file in files:
        path = file["key"]
        if prefix and path.startswith(prefix):
            path = path[len(prefix) :]
            if path.startswith("/"):
                path = path[1:]

        current = tree
        components = path.split("/")

        # Handle the path components, building the tree
        for i, component in enumerate(components):
            if not component:  # Skip empty components
                continue

            if i == len(components) - 1:  # Leaf node (file)
                current[component] = None
            else:  # Directory
                if component not in current:
                    current[component] = {}
                current = current[component]

    # Generate the tree as a string
    result = [f"{bucket_name}/{prefix}"]

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


def get_file_metadata(bucket_name: str, object_name: str) -> Dict[str, str]:
    """
    Get metadata of a file in MinIO/S3

    Args:
        bucket_name: Bucket name
        object_name: S3 object name (key)

    Returns:
        Dict: Metadata of the file
    """
    s3_client = get_minio_client()

    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=object_name)
        return response.get("Metadata", {})
    except ClientError as e:
        logger.error(f"Error getting metadata for {object_name} in bucket {bucket_name}: {e}")
        return {}


def get_workflow_files(bucket_name: str, user_id: str, workflow_id: str) -> List[Dict[str, Any]]:
    """
    Get all files for a specific workflow

    Args:
        bucket_name: Bucket name
        user_id: User ID
        workflow_id: Workflow ID

    Returns:
        List[Dict]: List of file information dictionaries
    """
    if not user_id or not workflow_id:
        return []

    # Define the prefix for this workflow's files
    prefix = f"user-{user_id}/{workflow_id}/"

    try:
        return list_files(bucket_name, prefix)
    except Exception as e:
        logger.error(f"Error getting workflow files: {e}")
        return []


def create_workflow_zip(
    bucket_name: str, user_id: str, workflow_id: str
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Create a zip file containing all files for a specific workflow

    Args:
        bucket_name: Bucket name
        user_id: User ID
        workflow_id: Workflow ID

    Returns:
        Tuple[Optional[bytes], Optional[str]]: Zip file content as bytes and filename, or (None, None) if failed
    """
    if not user_id or not workflow_id:
        return None, None

    # Get all files for this workflow
    files = get_workflow_files(bucket_name, user_id, workflow_id)

    if not files:
        return None, None

    # Create an in-memory zip file
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_info in files:
                object_name = file_info.get("key")
                if not object_name:  # Skip if key is None or empty
                    continue

                file_content = download_file(bucket_name, object_name)

                if not isinstance(file_content, bytes):
                    continue

                # Extract just the filename part from the object key
                filename = (
                    object_name.split("/")[-1]
                    if object_name and "/" in object_name
                    else object_name
                )
                if not filename:  # Skip if filename is None or empty
                    continue

                zip_file.writestr(filename, file_content)

        # Generate a timestamp for the zip filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"workflow_{workflow_id}_{timestamp}.zip"

        return zip_buffer.getvalue(), zip_filename
    except Exception as e:
        logger.error(f"Error creating workflow zip: {e}")
        return None, None


def extract_and_upload_zip(
    bucket_name: str, user_id: str, zip_content: bytes
) -> List[Dict[str, Any]]:
    """
    Extract files from a zip and upload them to MinIO under the input prefix

    Args:
        bucket_name: Bucket name
        user_id: User ID
        zip_content: Content of the zip file as bytes

    Returns:
        List[Dict]: List of information about the uploaded files
    """
    if not zip_content or not user_id:
        return []

    # Create an in-memory zip file from the content
    zip_buffer = io.BytesIO(zip_content)
    uploaded_files = []

    try:
        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            # Process each file in the zip
            for file_info in zip_file.infolist():
                # Skip directories
                if file_info.is_dir():
                    continue

                # Read the file content
                file_content = zip_file.read(file_info.filename)

                # Create object key with input prefix
                object_key = f"input/{user_id}/{file_info.filename}"

                # Upload the file to MinIO
                if upload_file(file_content, bucket_name, object_key):
                    uploaded_files.append(
                        {
                            "filename": file_info.filename,
                            "size": file_info.file_size,
                            "key": object_key,
                        }
                    )

        return uploaded_files
    except Exception as e:
        logger.error(f"Error extracting and uploading zip: {e}")
        return []
