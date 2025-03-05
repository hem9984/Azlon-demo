#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Unit tests for the file_handling module
"""

from unittest.mock import patch

import pytest

from src.utils.file_handling import PreFlightManager


class TestPreFlightManager:
    """Tests for the PreFlightManager class."""

    @pytest.fixture
    def file_server_mock(self):
        """Mock the file_server module."""
        with patch(
            "src.utils.file_handling.create_bucket_if_not_exists"
        ) as create_bucket_mock, patch(
            "src.utils.file_handling.upload_file"
        ) as upload_file_mock, patch(
            "src.utils.file_handling.download_file"
        ) as download_file_mock, patch(
            "src.utils.file_handling.list_files"
        ) as list_files_mock, patch(
            "src.utils.file_handling.generate_directory_tree"
        ) as gen_dir_tree_mock:
            create_bucket_mock.return_value = None
            upload_file_mock.return_value = True
            download_file_mock.return_value = b"test content"
            list_files_mock.return_value = [
                {"key": "user/run/file1.txt", "size": 100, "last_modified": "2023-01-01"},
                {"key": "user/run/dir1/file2.txt", "size": 200, "last_modified": "2023-01-02"},
            ]
            gen_dir_tree_mock.return_value = "├── file1.txt\n└── dir1\n    └── file2.txt"

            yield {
                "create_bucket": create_bucket_mock,
                "upload_file": upload_file_mock,
                "download_file": download_file_mock,
                "list_files": list_files_mock,
                "generate_directory_tree": gen_dir_tree_mock,
            }

    @pytest.fixture
    def preflight_manager(self):
        """Create an instance of PreFlightManager with test parameters."""
        manager = PreFlightManager(
            user_id="test-user", run_id="test-run", bucket_name="test-bucket"
        )
        return manager

    def test_init(self, preflight_manager, file_server_mock):
        """Test initialization."""
        assert preflight_manager.user_id == "test-user"
        assert preflight_manager.run_id == "test-run"
        assert preflight_manager.bucket_name == "test-bucket"
        assert preflight_manager.base_prefix == "test-user/test-run/"
        file_server_mock["create_bucket"].assert_called_once_with("test-bucket")

    def test_get_object_key(self, preflight_manager):
        """Test getting an object key with the correct prefix."""
        key = preflight_manager.get_object_key("file.txt")
        assert key == "test-user/test-run/file.txt"

        # Test with subdirectory
        key = preflight_manager.get_object_key("dir/file.txt")
        assert key == "test-user/test-run/dir/file.txt"

    def test_collect_and_upload_files_local(self, preflight_manager, file_server_mock, tmp_path):
        """Test collecting and uploading files from a local directory."""
        # Create temporary files
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file2 = dir1 / "file2.txt"
        file2.write_text("content2")

        # Call the function
        with patch("src.utils.file_handling.os.walk") as mock_walk:
            mock_walk.return_value = [
                (str(tmp_path), ["dir1"], ["file1.txt"]),
                (str(dir1), [], ["file2.txt"]),
            ]

            preflight_manager.collect_and_upload_files(str(tmp_path))

        # Assertions
        assert file_server_mock["upload_file"].call_count == 2

    def test_download_and_list_files(self, preflight_manager, file_server_mock):
        """Test downloading and listing files."""
        # Call the function
        files = preflight_manager.list_files()

        # Assertions
        file_server_mock["list_files"].assert_called_once_with("test-bucket", "test-user/test-run/")
        assert len(files) == 2
        assert files[0]["key"] == "user/run/file1.txt"

    def test_download_file(self, preflight_manager, file_server_mock):
        """Test downloading a file."""
        # Call the function
        content = preflight_manager.download_file("file.txt")

        # Assertions
        file_server_mock["download_file"].assert_called_once_with(
            "test-bucket", "test-user/test-run/file.txt"
        )
        assert content == b"test content"

    def test_generate_directory_tree(self, preflight_manager, file_server_mock):
        """Test generating a directory tree."""
        # Call the function
        tree = preflight_manager.generate_directory_tree()

        # Assertions
        file_server_mock["generate_directory_tree"].assert_called_once_with(
            "test-bucket", "test-user/test-run/"
        )
        assert "file1.txt" in tree
        assert "dir1" in tree
        assert "file2.txt" in tree
