"""
Tests for the workflow module in src/workflows/workflow.py
"""
import os
import time
import pytest
import shutil
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.workflows.workflow import AutonomousCodingWorkflow, WorkflowInputParams


@pytest.fixture
def mock_workflow_step():
    """
    Mock the workflow.step function for testing
    """
    with patch('restack_ai.workflow.workflow.step') as mock_step:
        mock_step.return_value = AsyncMock()
        yield mock_step


@pytest.fixture
def mock_preflightmanager():
    """
    Mock the PreFlightManager for testing
    """
    with patch('src.workflows.workflow.PreFlightManager') as mock_pfm:
        mock_instance = MagicMock()
        mock_pfm.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_codeinclusionmanager():
    """
    Mock the CodeInclusionManager for testing
    """
    with patch('src.workflows.workflow.CodeInclusionManager') as mock_cm:
        mock_instance = MagicMock()
        mock_cm.return_value = mock_instance
        mock_instance.build_code_context.return_value = "Test code context"
        yield mock_instance


@pytest.fixture
def mock_create_bucket():
    """
    Mock the create_bucket_if_not_exists function
    """
    with patch('src.workflows.workflow.create_bucket_if_not_exists') as mock_create:
        yield mock_create


@pytest.fixture
def mock_makedirs():
    """
    Mock os.makedirs to avoid filesystem operations
    """
    with patch('os.makedirs') as mock_makedirs:
        yield mock_makedirs


@pytest.fixture
def mock_path_exists():
    """
    Mock os.path.exists
    """
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False
        yield mock_exists


@pytest.fixture
def workflow_instance():
    """
    Create an instance of the workflow class
    """
    return AutonomousCodingWorkflow()


@patch('time.time')
async def test_workflow_initialization(mock_time, 
                                      workflow_instance, 
                                      mock_create_bucket, 
                                      mock_makedirs,
                                      mock_path_exists):
    """Test the workflow initialization process"""
    # Set fixed timestamp for testing
    mock_time.return_value = 1234567890.123
    timestamp = int(1234567890.123 * 1000)
    
    # Create input parameters
    input_params = WorkflowInputParams(
        user_prompt="Create a hello world app",
        test_conditions="Should print hello world",
        user_id="test-user"
    )
    
    # Mock the run method to avoid executing the whole workflow
    with patch.object(workflow_instance, '_execute_iteration', AsyncMock()):
        with patch.object(workflow_instance, '_finalize_workspace', AsyncMock()):
            # Call the run method with the input parameters
            await workflow_instance.run(input_params)
            
            # Verify bucket was created
            mock_create_bucket.assert_called_once_with("azlon-files")
            
            # Verify directories were created
            assert mock_makedirs.call_count >= 3
            
            # Check that directories for user ID and run ID are created
            mock_makedirs_calls = mock_makedirs.call_args_list
            assert any("test-user" in str(call) for call in mock_makedirs_calls)
            assert any(str(timestamp) in str(call) for call in mock_makedirs_calls)


@patch('time.time')
async def test_workflow_with_preflight_files(mock_time,
                                           workflow_instance,
                                           mock_preflightmanager,
                                           mock_workflow_step,
                                           mock_makedirs,
                                           mock_path_exists,
                                           mock_create_bucket):
    """Test workflow execution with pre-flight files present"""
    # Set fixed timestamp for testing
    mock_time.return_value = 1234567890.123
    
    # Mock preflight manager to return that files exist
    mock_preflightmanager.has_input_files.return_value = True
    
    # Mock the preflight result
    preflight_mock = MagicMock()
    preflight_mock.runOutput = "Preflight test output"
    mock_workflow_step.return_value = preflight_mock
    
    # Create input parameters
    input_params = WorkflowInputParams(
        user_prompt="Create a hello world app",
        test_conditions="Should print hello world",
        user_id="test-user"
    )
    
    # Mock workflow helper methods to avoid executing everything
    with patch.object(workflow_instance, '_copy_preflight_workspace'):
        with patch.object(workflow_instance, '_execute_iteration', AsyncMock()):
            with patch.object(workflow_instance, '_finalize_workspace', AsyncMock()):
                # Execute the workflow
                await workflow_instance.run(input_params)
                
                # Verify preflight was checked and executed
                mock_preflightmanager.has_input_files.assert_called_once()
                mock_workflow_step.assert_called_once()
                
                # Verify the context was passed correctly
                context_arg = mock_workflow_step.call_args[1]["task_queue_context"]
                assert context_arg["user_id"] == "test-user"
                assert "run_id" in context_arg


@patch('time.time')
async def test_workflow_without_preflight_files(mock_time,
                                              workflow_instance,
                                              mock_preflightmanager,
                                              mock_codeinclusionmanager,
                                              mock_workflow_step,
                                              mock_makedirs,
                                              mock_path_exists,
                                              mock_create_bucket):
    """Test workflow execution without pre-flight files"""
    # Set fixed timestamp for testing
    mock_time.return_value = 1234567890.123
    
    # Mock preflight manager to return that no files exist
    mock_preflightmanager.has_input_files.return_value = False
    
    # Create input parameters
    input_params = WorkflowInputParams(
        user_prompt="Create a hello world app",
        test_conditions="Should print hello world",
        user_id="test-user"
    )
    
    # Mock workflow helper methods to avoid executing everything
    with patch.object(workflow_instance, '_execute_iteration', AsyncMock()):
        with patch.object(workflow_instance, '_finalize_workspace', AsyncMock()):
            # Execute the workflow
            await workflow_instance.run(input_params)
            
            # Verify preflight was checked but not executed
            mock_preflightmanager.has_input_files.assert_called_once()
            assert mock_workflow_step.call_count == 0


@patch('time.time')
async def test_workflow_iteration_execution(mock_time,
                                          workflow_instance,
                                          mock_preflightmanager,
                                          mock_codeinclusionmanager,
                                          mock_workflow_step,
                                          mock_makedirs,
                                          mock_path_exists,
                                          mock_create_bucket):
    """Test workflow iteration execution"""
    # Set fixed timestamp for testing
    mock_time.return_value = 1234567890.123
    
    # Mock preflight manager to return that no files exist
    mock_preflightmanager.has_input_files.return_value = False
    
    # Create input parameters
    input_params = WorkflowInputParams(
        user_prompt="Create a hello world app",
        test_conditions="Should print hello world",
        user_id="test-user"
    )
    
    # Create mock validation results for iteration control
    mock_validation_result = MagicMock()
    mock_validation_result.success = True
    mock_workflow_step.return_value = mock_validation_result
    
    # Mock the _execute_iteration method to use real implementation
    real_method = workflow_instance._execute_iteration
    
    # Execute with patched methods
    with patch.object(workflow_instance, '_execute_iteration', wraps=real_method):
        with patch.object(workflow_instance, '_finalize_workspace', AsyncMock()):
            # Run the workflow
            result = await workflow_instance.run(input_params)
            
            # Should succeed after first iteration due to our mock
            assert mock_workflow_step.call_count > 0
