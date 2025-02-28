"""
Tests for file_handling module.
"""
import pytest
import os
import subprocess
import shutil
from unittest.mock import patch, MagicMock, mock_open
from src.utils.file_handling import (
    GitManager, CodeInclusionManager, PreFlightManager, run_tree_command
)


@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run."""
    with patch('src.utils.file_handling.subprocess.run') as mock_run:
        yield mock_run


@pytest.fixture
def mock_os_path_isdir():
    """Fixture to mock os.path.isdir."""
    with patch('src.utils.file_handling.os.path.isdir') as mock_isdir:
        yield mock_isdir


@pytest.fixture
def mock_os_path_isfile():
    """Fixture to mock os.path.isfile."""
    with patch('src.utils.file_handling.os.path.isfile') as mock_isfile:
        yield mock_isfile


@pytest.fixture
def mock_os_makedirs():
    """Fixture to mock os.makedirs."""
    with patch('src.utils.file_handling.os.makedirs') as mock_makedirs:
        yield mock_makedirs


@pytest.fixture
def mock_os_listdir():
    """Fixture to mock os.listdir."""
    with patch('src.utils.file_handling.os.listdir') as mock_listdir:
        yield mock_listdir


@pytest.fixture
def mock_shutil_copy2():
    """Fixture to mock shutil.copy2."""
    with patch('src.utils.file_handling.shutil.copy2') as mock_copy2:
        yield mock_copy2


@pytest.fixture
def mock_shutil_copytree():
    """Fixture to mock shutil.copytree."""
    with patch('src.utils.file_handling.shutil.copytree') as mock_copytree:
        yield mock_copytree


@pytest.fixture
def mock_open_file():
    """Fixture to mock open function."""
    with patch('builtins.open', mock_open(read_data="test content")) as mock_file:
        yield mock_file


# GitManager Tests
def test_git_manager_init_new_repo(mock_os_path_isdir, mock_os_makedirs, mock_subprocess_run):
    """Test GitManager initialization with a new repository."""
    # Setup
    mock_os_path_isdir.side_effect = [True, False]  # repo_path exists, .git doesn't
    
    # Execute
    git_manager = GitManager("/test/path")
    
    # Assert
    mock_os_makedirs.assert_not_called()  # repo_path already exists
    assert mock_subprocess_run.call_count == 3  # git init, config user.name, config user.email
    assert git_manager.repo_path == "/test/path"


def test_git_manager_init_existing_repo(mock_os_path_isdir, mock_os_makedirs):
    """Test GitManager initialization with an existing repository."""
    # Setup
    mock_os_path_isdir.return_value = True  # Both repo_path and .git exist
    
    # Execute
    git_manager = GitManager("/test/path")
    
    # Assert
    mock_os_makedirs.assert_not_called()
    assert git_manager.repo_path == "/test/path"


def test_git_manager_merge_llm_changes(mock_subprocess_run, mock_os_path_isdir, mock_open_file):
    """Test GitManager merge_llm_changes method."""
    # Setup
    mock_os_path_isdir.return_value = True
    git_manager = GitManager("/test/path")
    mock_subprocess_run.reset_mock()  # Clear calls from init
    
    # Execute
    git_manager.merge_llm_changes(
        llm_dockerfile="FROM python:3.9",
        llm_files=[
            {"filename": "test.py", "content": "print('hello')"}
        ]
    )
    
    # Assert
    # Check git commands were called: checkout, branch, add, commit, checkout, merge
    assert mock_subprocess_run.call_count >= 6


# CodeInclusionManager Tests
def test_code_inclusion_manager_init():
    """Test CodeInclusionManager initialization."""
    manager = CodeInclusionManager("/test/path")
    assert manager.repo_path == "/test/path"
    assert manager.token_count == 0


def test_build_code_context(mock_os_path_isfile, mock_os_listdir, mock_open_file):
    """Test build_code_context method."""
    # Setup
    mock_os_path_isfile.return_value = True
    mock_os_listdir.return_value = ["file1.py", "file2.py", "file3.csv"]
    manager = CodeInclusionManager("/test/path")
    
    # Execute
    with patch.object(manager, '_build_directory_tree', return_value="tree output"):
        with patch.object(manager, '_read_dockerfile', return_value="FROM python:3.9"):
            with patch.object(manager, '_gather_files', return_value=[
                {"filename": "file1.py", "content": "print('hello')"}
            ]):
                result = manager.build_code_context(
                    user_prompt="Create a script",
                    test_conditions="Must work",
                    previous_output="Output from previous run"
                )
    
    # Assert
    assert result["dirTree"] == "tree output"
    assert result["dockerfile"] == "FROM python:3.9"
    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "file1.py"


# PreFlightManager Tests
def test_has_input_files(mock_os_path_isdir, mock_os_listdir):
    """Test has_input_files method."""
    # Setup
    mock_os_path_isdir.return_value = True
    mock_os_listdir.return_value = ["file1.py"]
    manager = PreFlightManager()
    
    # Execute
    result = manager.has_input_files()
    
    # Assert
    assert result is True


def test_perform_preflight_merge_and_run(mock_os_path_isdir, mock_os_makedirs, mock_os_listdir, mock_subprocess_run):
    """Test perform_preflight_merge_and_run method."""
    # Setup
    mock_os_path_isdir.return_value = True
    mock_os_listdir.return_value = ["file1.py", "Dockerfile"]
    manager = PreFlightManager()
    
    # Mock methods to isolate the test
    with patch.object(manager, '_collect_input_files', return_value={
        "files": [{"filename": "file1.py", "content": "print('hello')"}],
        "dockerfile": "FROM python:3.9"
    }):
        with patch('src.utils.file_handling.run_tree_command', return_value="tree output"):
            # Execute
            result = manager.perform_preflight_merge_and_run()
    
    # Assert
    assert result.dirTree == "tree output"
    assert "docker build" in result.runOutput or "docker run" in result.runOutput


# Helper function tests
def test_run_tree_command(mock_subprocess_run):
    """Test run_tree_command function."""
    # Setup
    mock_subprocess_run.return_value = MagicMock(
        stdout="directory tree output",
        returncode=0
    )
    
    # Execute
    result = run_tree_command("/test/directory")
    
    # Assert
    mock_subprocess_run.assert_called_once()
    assert result == "directory tree output"


def test_run_tree_command_error(mock_subprocess_run):
    """Test run_tree_command function when command fails."""
    # Setup
    mock_subprocess_run.return_value = MagicMock(
        stdout="",
        stderr="error output",
        returncode=1
    )
    
    # Execute
    result = run_tree_command("/test/directory")
    
    # Assert
    mock_subprocess_run.assert_called_once()
    assert "Error" in result
