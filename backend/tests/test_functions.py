"""
Tests for functions module.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import subprocess
from src.functions.functions import (
    generate_code, run_locally, validate_output, pre_flight_run,
    RunCodeInput, RunCodeOutput, GenerateCodeInput, ValidateCodeInput
)


@pytest.fixture
def mock_get_prompts():
    """Fixture to mock get_prompts."""
    with patch('src.functions.functions.get_prompts') as mock_func:
        mock_func.return_value = {
            "generate_code_prompt": "test prompt for generate_code",
            "validate_output_prompt": "test prompt for validate_output"
        }
        yield mock_func


@pytest.fixture
def mock_get_all_memories():
    """Fixture to mock get_all_memories."""
    with patch('src.functions.functions.get_all_memories') as mock_func:
        mock_func.return_value = [{"content": "test memory"}]
        yield mock_func


@pytest.fixture
def mock_add_memory():
    """Fixture to mock add_memory."""
    with patch('src.functions.functions.add_memory') as mock_func:
        yield mock_func


@pytest.fixture
def mock_baml_client():
    """Fixture to mock BAML client."""
    with patch('src.functions.functions.b') as mock_client:
        mock_client.GenerateCode = AsyncMock()
        mock_client.ValidateOutput = AsyncMock()
        yield mock_client


@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run."""
    with patch('src.functions.functions.subprocess.run') as mock_run:
        yield mock_run


@pytest.fixture
def mock_preflight_manager():
    """Fixture to mock PreFlightManager."""
    with patch('src.utils.file_handling.PreFlightManager') as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_generate_code(mock_get_prompts, mock_get_all_memories, mock_add_memory, mock_baml_client):
    """Test generate_code function."""
    # Setup
    input_data = GenerateCodeInput(
        userPrompt="Create a hello world script",
        testConditions="Must print hello world",
        dirTree=None,
        preflightResult=None,
        validationResult=None,
        memories=None
    )
    expected_result = MagicMock()
    mock_baml_client.GenerateCode.return_value = expected_result
    
    # Execute
    result = await generate_code(input_data)
    
    # Assert
    mock_get_prompts.assert_called_once()
    mock_get_all_memories.assert_called_once_with(agent_id="generate_code")
    mock_baml_client.GenerateCode.assert_called_once()
    mock_add_memory.assert_called_once_with(expected_result, agent_id="generate_code")
    assert result == expected_result


@pytest.mark.asyncio
async def test_run_locally_success(mock_subprocess_run):
    """Test run_locally function when build and run succeed."""
    # Setup
    input_data = RunCodeInput(repo_path="/test/path")
    mock_subprocess_run.side_effect = [
        MagicMock(returncode=0),  # build succeeds
        MagicMock(returncode=0, stdout="test output")  # run succeeds
    ]
    
    # Execute
    result = await run_locally(input_data)
    
    # Assert
    assert mock_subprocess_run.call_count == 2
    assert result.output == "test output"


@pytest.mark.asyncio
async def test_run_locally_build_failure(mock_subprocess_run):
    """Test run_locally function when build fails."""
    # Setup
    input_data = RunCodeInput(repo_path="/test/path")
    mock_subprocess_run.return_value = MagicMock(
        returncode=1, 
        stderr="build error", 
        stdout=""
    )
    
    # Execute
    result = await run_locally(input_data)
    
    # Assert
    mock_subprocess_run.assert_called_once()
    assert result.output == "build error"


@pytest.mark.asyncio
async def test_run_locally_run_failure(mock_subprocess_run):
    """Test run_locally function when run fails."""
    # Setup
    input_data = RunCodeInput(repo_path="/test/path")
    mock_subprocess_run.side_effect = [
        MagicMock(returncode=0),  # build succeeds
        MagicMock(returncode=1, stderr="run error", stdout="")  # run fails
    ]
    
    # Execute
    result = await run_locally(input_data)
    
    # Assert
    assert mock_subprocess_run.call_count == 2
    assert result.output == "run error"


@pytest.mark.asyncio
async def test_validate_output(mock_get_prompts, mock_get_all_memories, mock_add_memory, mock_baml_client):
    """Test validate_output function."""
    # Setup
    input_data = ValidateCodeInput(
        dockerfile="FROM python:3.9",
        files=[],
        output="hello world",
        userPrompt="Create a hello world script",
        testConditions="Must print hello world",
        iteration=1,
        memories=None,
        dirTree=None
    )
    expected_result = MagicMock()
    mock_baml_client.ValidateOutput.return_value = expected_result
    
    # Execute
    result = await validate_output(input_data)
    
    # Assert
    mock_get_prompts.assert_called_once()
    mock_get_all_memories.assert_called_once_with(agent_id="validate_output")
    mock_baml_client.ValidateOutput.assert_called_once()
    mock_add_memory.assert_called_once_with(expected_result, agent_id="validate_output")
    assert result == expected_result


@pytest.mark.asyncio
async def test_pre_flight_run(mock_preflight_manager):
    """Test pre_flight_run function."""
    # Setup
    expected_result = MagicMock()
    mock_preflight_manager.perform_preflight_merge_and_run.return_value = expected_result
    
    # Execute
    result = await pre_flight_run()
    
    # Assert
    mock_preflight_manager.perform_preflight_merge_and_run.assert_called_once()
    assert result == expected_result
