"""
Tests for the functions module in src/functions/functions.py
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from src.functions.functions import (
    generate_code,
    run_with_e2b,
    validate_output,
    pre_flight_run,
    GenerateCodeInput,
    RunCodeInput,
    ValidateCodeInput,
    PreFlightInput
)


@pytest.fixture
def mock_function_info():
    """
    Mock the function.info() method to return context with user_id and run_id
    """
    with patch('src.functions.functions.function.info') as mock_info:
        # Create a mock object with task_queue_context property
        mock_info_obj = MagicMock()
        context = {"user_id": "test-user", "run_id": "test-run-123"}
        # Set the task_queue_context property on the mock
        type(mock_info_obj).task_queue_context = PropertyMock(return_value=context)
        mock_info.return_value = mock_info_obj
        yield mock_info


@pytest.fixture
def mock_baml_client():
    """
    Mock the BAML client for testing
    """
    with patch('src.functions.functions.b') as mock_b:
        # Mock the generate_code method
        mock_b.generate_code = AsyncMock()
        mock_b.generate_code.return_value = MagicMock(files=[
            {"path": "test.py", "content": "print('hello world')"}
        ])
        
        # Mock the validate_output method
        mock_b.validate_output = AsyncMock()
        mock_validation_result = MagicMock()
        mock_validation_result.success = True
        mock_validation_result.validation_feedback = "Tests passed successfully"
        mock_b.validate_output.return_value = mock_validation_result
        
        yield mock_b


@pytest.fixture
def mock_prompts():
    """
    Mock the get_prompts function
    """
    with patch('src.functions.functions.get_prompts') as mock_get_prompts:
        mock_get_prompts.return_value = {
            "system_prompt": "Test system prompt",
            "generate_code_prompt": "Test generate code prompt",
            "validate_output_prompt": "Test validate output prompt"
        }
        yield mock_get_prompts


@pytest.fixture
def mock_pfm():
    """
    Mock the PreFlightManager for testing
    """
    with patch('src.functions.functions.PreFlightManager') as mock_pfm_class:
        mock_pfm = MagicMock()
        mock_pfm_class.return_value = mock_pfm
        
        # Set up the mock methods
        mock_pfm.get_workspace_path.return_value = "/tmp/test-workspace"
        mock_pfm.has_dockerfile.return_value = True
        mock_pfm.upload_workspace_files.return_value = ["test.py"]
        
        yield mock_pfm


@pytest.fixture
def mock_e2b_runner():
    """
    Mock the E2BRunner for testing
    """
    with patch('src.functions.functions.E2BRunner') as mock_e2b_class:
        mock_e2b = MagicMock()
        mock_e2b_class.return_value = mock_e2b
        
        # Set up mock methods
        mock_e2b.init_sandbox.return_value = True
        mock_e2b.upload_files.return_value = []
        mock_e2b.install_packages.return_value = ""
        mock_e2b.run_command.return_value = MagicMock(
            stdout="Test output", 
            stderr="", 
            exit_code=0
        )
        mock_e2b.close.return_value = None
        
        yield mock_e2b


@pytest.mark.asyncio
async def test_generate_code(mock_function_info, mock_baml_client, mock_prompts):
    """Test the generate_code function"""
    # Create input for the function
    input_data = GenerateCodeInput(
        user_prompt="Create a hello world program", 
        code_context="Example context",
        test_conditions="Should print hello world"
    )
    
    # Call the function
    result = await generate_code(input_data)
    
    # Verify BAML client was called
    mock_baml_client.generate_code.assert_called_once()
    
    # Verify the result contains the file from the mock
    assert len(result.files) == 1
    assert result.files[0]["path"] == "test.py"
    assert result.files[0]["content"] == "print('hello world')"


@pytest.mark.asyncio
async def test_validate_output(mock_function_info, mock_baml_client, mock_prompts):
    """Test the validate_output function"""
    # Create input for the function
    input_data = ValidateCodeInput(
        user_prompt="Create a hello world program",
        test_conditions="Should print hello world",
        code_context="print('hello world')",
        run_output="hello world"
    )
    
    # Call the function
    result = await validate_output(input_data)
    
    # Verify BAML client was called
    mock_baml_client.validate_output.assert_called_once()
    
    # Verify the result
    assert result.success is True
    assert "Tests passed successfully" in result.validation_feedback


@pytest.mark.asyncio
async def test_run_with_e2b(mock_function_info, mock_e2b_runner):
    """Test the run_with_e2b function"""
    # Create input for the function
    input_data = RunCodeInput(
        repo_path="/test/repo",
        user_id="test-user",
        run_id="test-run-123"
    )
    
    # Call the function
    result = await run_with_e2b(input_data)
    
    # Verify E2BRunner was initialized and methods were called
    mock_e2b_runner.init_sandbox.assert_called_once()
    mock_e2b_runner.upload_files.assert_called_once()
    mock_e2b_runner.run_command.assert_called()
    mock_e2b_runner.close.assert_called_once()
    
    # Verify the result contains the output
    assert "Test output" in result.output


@pytest.mark.asyncio
async def test_pre_flight_run(mock_function_info, mock_pfm, mock_e2b_runner):
    """Test the pre_flight_run function with Dockerfile"""
    # Create input for the function
    input_data = PreFlightInput(
        user_id="test-user",
        run_id="test-run-123"
    )
    
    # Call the function
    result = await pre_flight_run(input_data)
    
    # Verify PreFlightManager was used
    mock_pfm.get_workspace_path.assert_called()
    mock_pfm.has_dockerfile.assert_called_once()
    
    # Verify E2BRunner was used since we mocked has_dockerfile to True
    mock_e2b_runner.init_sandbox.assert_called_once()
    mock_e2b_runner.upload_files.assert_called_once()
    
    # Verify the result contains dockerOutput
    assert hasattr(result, "dockerOutput")
    assert hasattr(result, "runOutput")


@pytest.mark.asyncio
async def test_pre_flight_run_no_dockerfile(mock_function_info, mock_pfm):
    """Test the pre_flight_run function without Dockerfile"""
    # Override has_dockerfile to return False
    mock_pfm.has_dockerfile.return_value = False
    
    # Create input for the function
    input_data = PreFlightInput(
        user_id="test-user",
        run_id="test-run-123"
    )
    
    # Call the function
    result = await pre_flight_run(input_data)
    
    # Verify PreFlightManager was used
    mock_pfm.get_workspace_path.assert_called()
    mock_pfm.has_dockerfile.assert_called_once()
    
    # Verify the result contains the skipped message
    assert hasattr(result, "dockerOutput")
    assert "Skipping" in result.dockerOutput
    assert hasattr(result, "runOutput")
