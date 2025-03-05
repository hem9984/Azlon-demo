#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Unit tests for the file_server module (MinIO integration)
"""

import io
from unittest.mock import MagicMock, patch

import pytest

from src.file_server import (
    create_bucket_if_not_exists,
    delete_file,
    download_file,
    generate_directory_tree,
    list_files,
    upload_file,
)


class TestFileServer:
    """Tests for the file_server module."""

    @pytest.fixture
    def minio_client_mock(self):
        """Mock the MinIO/S3 client."""
        with patch("src.file_server.get_minio_client") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_create_bucket_if_not_exists_new(self, minio_client_mock):
        """Test creating a new bucket."""
        # Set up mocks
        minio_client_mock.list_buckets.return_value = {"Buckets": []}
        minio_client_mock.create_bucket.return_value = {}

        # Call the function
        create_bucket_if_not_exists("test-bucket")

        # Assertions
        minio_client_mock.list_buckets.assert_called_once()
        minio_client_mock.create_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_create_bucket_if_not_exists_already_exists(self, minio_client_mock):
        """Test with an existing bucket."""
        # Set up mocks
        minio_client_mock.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}

        # Call the function
        create_bucket_if_not_exists("test-bucket")

        # Assertions
        minio_client_mock.list_buckets.assert_called_once()
        minio_client_mock.create_bucket.assert_not_called()

    def test_upload_file_from_path(self, minio_client_mock, tmp_path):
        """Test uploading a file from a file path."""
        # Create a temporary file
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("test content")

        # Call the function
        upload_file(str(file_path), "test-bucket", "test-key")

        # Assertions
        minio_client_mock.upload_file.assert_called_once_with(
            str(file_path), "test-bucket", "test-key"
        )

    def test_upload_file_from_buffer(self, minio_client_mock):
        """Test uploading a file from a buffer."""
        # Create a buffer with content
        buffer = io.BytesIO(b"test content")

        # Call the function
        upload_file(buffer, "test-bucket", "test-key")

        # Assertions
        minio_client_mock.upload_fileobj.assert_called_once()
        args, _ = minio_client_mock.upload_fileobj.call_args
        assert args[0] == buffer
        assert args[1] == "test-bucket"
        assert args[2] == "test-key"

    def test_download_file(self, minio_client_mock):
        """Test downloading a file."""
        # Set up mock response
        response = {"Body": io.BytesIO(b"test content")}
        minio_client_mock.get_object.return_value = response

        # Call the function
        result = download_file("test-bucket", "test-key")

        # Assertions
        minio_client_mock.get_object.assert_called_once_with(Bucket="test-bucket", Key="test-key")
        assert result == b"test content"

    def test_list_files(self, minio_client_mock):
        """Test listing files."""
        # Set up mock response
        objects = {
            "Contents": [
                {"Key": "test/key1.txt", "Size": 10, "LastModified": "2023-01-01"},
                {"Key": "test/key2.txt", "Size": 20, "LastModified": "2023-01-02"},
            ]
        }
        minio_client_mock.list_objects_v2.return_value = objects

        # Call the function
        result = list_files("test-bucket", "test/")

        # Assertions
        minio_client_mock.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="test/"
        )
        assert len(result) == 2
        assert result[0]["key"] == "test/key1.txt"
        assert result[1]["key"] == "test/key2.txt"

    def test_delete_file(self, minio_client_mock):
        """Test deleting a file."""
        # Call the function
        delete_file("test-bucket", "test-key")

        # Assertions
        minio_client_mock.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-key"
        )

    def test_generate_directory_tree(self, minio_client_mock):
        """Test generating a directory tree."""
        # Set up mock response
        objects = {
            "Contents": [
                {"Key": "user/run/file1.txt", "Size": 10, "LastModified": "2023-01-01"},
                {"Key": "user/run/dir1/file2.txt", "Size": 20, "LastModified": "2023-01-02"},
                {"Key": "user/run/dir1/file3.txt", "Size": 30, "LastModified": "2023-01-03"},
                {"Key": "user/run/dir2/subdir/file4.txt", "Size": 40, "LastModified": "2023-01-04"},
            ]
        }
        minio_client_mock.list_objects_v2.return_value = objects

        # Call the function
        result = generate_directory_tree("test-bucket", "user/run/")

        # Assertions
        minio_client_mock.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="user/run/"
        )
        assert "file1.txt" in result
        assert "dir1" in result
        assert "dir2" in result
        assert "subdir" in result
