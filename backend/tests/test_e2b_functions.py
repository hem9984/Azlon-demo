#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Unit tests for the e2b_functions module
"""

from unittest.mock import Mock, patch

import pytest

from src.e2b_functions import E2BRunner


class TestE2BRunner:
    """Tests for the E2BRunner class."""

    @pytest.fixture
    def e2b_mock(self):
        """Mock the E2B SDK."""
        with patch("src.e2b_functions.Sandbox") as mock_sandbox_class:
            sandbox_instance = Mock()
            mock_sandbox_class.return_value = sandbox_instance
            yield sandbox_instance

    @pytest.fixture
    def sandbox_class_mock(self):
        """Mock for the Sandbox class itself."""
        with patch("src.e2b_functions.Sandbox") as mock_sandbox_class:
            yield mock_sandbox_class

    @pytest.fixture
    def runner(self):
        """Create an instance of E2BRunner."""
        runner = E2BRunner()
        yield runner

    def test_init_sandbox(self, runner, sandbox_class_mock):
        """Test initializing a sandbox."""
        # Mock configuration
        with patch("src.e2b_functions.os.environ.get") as mock_getenv:
            mock_getenv.return_value = "test-api-key"

            # Call the function
            sandbox = runner.init_sandbox()

            # Assertions
            assert sandbox is not None

            # Check that the Sandbox constructor was called once with correct arguments
            sandbox_class_mock.assert_called_once_with(
                template=runner.template, api_key=runner.api_key
            )

    def test_install_packages(self, runner, e2b_mock):
        """Test installing packages in the sandbox."""
        # Setup mock response for commands.run
        command_result = Mock()
        command_result.exit_code = 0
        command_result.stdout = "Successfully installed packages"
        e2b_mock.commands.run.return_value = command_result

        # Call the function
        result = runner.install_packages(e2b_mock, ["pytest", "requests"])

        # Assertions
        assert result is True
        e2b_mock.commands.run.assert_called_once()
        args, _ = e2b_mock.commands.run.call_args
        assert "pip install" in args[0]
        assert "pytest" in args[0]
        assert "requests" in args[0]

    def test_install_packages_failure(self, runner, e2b_mock):
        """Test failure when installing packages."""
        # Setup mock response for commands.run
        command_result = Mock()
        command_result.exit_code = 1
        command_result.stderr = "Error installing packages"
        e2b_mock.commands.run.return_value = command_result

        # Call the function
        result = runner.install_packages(e2b_mock, ["non-existent-package"])

        # Assertions
        assert result is False

    def test_upload_file_to_e2b(self, runner, e2b_mock):
        """Test uploading a file to E2B."""
        # Setup file content and mock
        file_content = b"test content"

        # Call the function
        result = runner.upload_file_to_e2b(e2b_mock, file_content, "/tmp/test.txt")

        # Assertions
        assert result is True
        e2b_mock.files.write.assert_called_once_with("/tmp/test.txt", file_content)

    def test_upload_file_to_e2b_failure(self, runner, e2b_mock):
        """Test failure when uploading a file to E2B."""
        # Setup mock to raise an exception
        e2b_mock.files.write.side_effect = Exception("Upload failed")

        # Call the function
        result = runner.upload_file_to_e2b(e2b_mock, b"content", "/tmp/test.txt")

        # Assertions
        assert result is False

    def test_download_file_from_e2b(self, runner, e2b_mock):
        """Test downloading a file from E2B."""
        # Setup mock response
        e2b_mock.files.read.return_value = b"test content"

        # Call the function
        result = runner.download_file_from_e2b(e2b_mock, "/tmp/test.txt")

        # Assertions
        assert result == b"test content"
        e2b_mock.files.read.assert_called_once_with("/tmp/test.txt")

    def test_download_file_from_e2b_failure(self, runner, e2b_mock):
        """Test failure when downloading a file from E2B."""
        # Setup mock to raise an exception
        e2b_mock.files.read.side_effect = Exception("Download failed")

        # Call the function
        result = runner.download_file_from_e2b(e2b_mock, "/tmp/test.txt")

        # Assertions
        assert result is None

    def test_run_command_in_e2b(self, runner, e2b_mock):
        """Test running a command in E2B."""
        # Setup mock response
        command_result = Mock()
        command_result.exit_code = 0
        command_result.stdout = "Command output"
        e2b_mock.commands.run.return_value = command_result

        # Call the function
        result = runner.run_command_in_e2b(e2b_mock, "echo 'test'")

        # Assertions
        assert result.exit_code == 0
        assert result.stdout == "Command output"
        e2b_mock.commands.run.assert_called_once_with("echo 'test'")

    def test_file_exists_in_e2b(self, runner, e2b_mock):
        """Test checking if a file exists in E2B."""
        # Setup mock response
        command_result = Mock()
        command_result.stdout = "exists"
        e2b_mock.commands.run.return_value = command_result

        # Call the function
        result = runner._file_exists_in_e2b(e2b_mock, "/tmp/test.txt")

        # Assertions
        assert result is True
        e2b_mock.commands.run.assert_called_once()

    def test_file_not_exists_in_e2b(self, runner, e2b_mock):
        """Test checking if a file does not exist in E2B."""
        # Setup mock response
        command_result = Mock()
        command_result.stdout = "not exists"
        e2b_mock.commands.run.return_value = command_result

        # Call the function
        result = runner._file_exists_in_e2b(e2b_mock, "/tmp/nonexistent.txt")

        # Assertions
        assert result is False
        e2b_mock.commands.run.assert_called_once()

    def test_generate_directory_tree(self, runner, e2b_mock):
        """Test generating a directory tree in E2B."""
        # Setup mock response for both commands
        install_result = Mock()
        install_result.exit_code = 0

        tree_result = Mock()
        tree_result.exit_code = 0
        tree_result.stdout = ".\n├── file1.txt\n└── dir1\n    └── file2.txt"

        # Configure the mock to return different values for each call
        e2b_mock.commands.run.side_effect = [install_result, tree_result]

        # Call the function
        result = runner.generate_directory_tree(e2b_mock, "/tmp")

        # Assertions
        assert "file1.txt" in result
        assert "dir1" in result
        assert "file2.txt" in result
        assert e2b_mock.commands.run.call_count == 2
        # Verify the specific calls made
        e2b_mock.commands.run.assert_any_call("apt-get update && apt-get install -y tree || true")
        e2b_mock.commands.run.assert_any_call("cd /tmp && tree -a")
