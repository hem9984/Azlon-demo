"""
Tests for the main API endpoints in main.py
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app
    """
    return TestClient(app)


@pytest.fixture
def mock_client():
    """
    Create a mock Restack client
    """
    with patch("main.client") as mock_client:
        mock_client.schedule_workflow = AsyncMock(return_value="test-run-id")
        mock_client.get_workflow_result = AsyncMock(return_value={"status": "completed"})
        yield mock_client


def test_prompts_endpoint(client):
    """Test the prompts endpoint returns expected prompts"""
    with patch("main.get_prompts") as mock_get_prompts:
        # Mock the prompts data
        mock_get_prompts.return_value = {
            "system_prompt": "Test system prompt",
            "generate_code_prompt": "Test generate code prompt",
            "validate_output_prompt": "Test validate output prompt",
        }

        response = client.get("/prompts")
        assert response.status_code == 200
        assert "system_prompt" in response.json()
        assert "generate_code_prompt" in response.json()
        assert "validate_output_prompt" in response.json()


def test_run_workflow_endpoint(client, mock_client):
    """Test the run_workflow endpoint with proper parameters"""
    # Prepare test data
    test_data = {
        "user_prompt": "Create a Python hello world script",
        "test_conditions": "Should print 'hello world'",
        "user_id": "test-user",
    }

    # Call the endpoint
    response = client.post("/run_workflow", json=test_data)

    # Verify response
    assert response.status_code == 200
    assert "workflow_id" in response.json()
    assert "result" in response.json()  # Result contains the workflow output
    assert "user_id" in response.json()

    # Verify client was called correctly
    mock_client.schedule_workflow.assert_called_once()
    call_args = mock_client.schedule_workflow.call_args[1]
    assert call_args["workflow_name"] == "AutonomousCodingWorkflow"
    assert "test-user" in call_args["workflow_id"]
    assert call_args["input"]["user_prompt"] == test_data["user_prompt"]
    assert call_args["input"]["test_conditions"] == test_data["test_conditions"]
    assert call_args["input"]["user_id"] == test_data["user_id"]


def test_run_workflow_with_header_user_id(client, mock_client):
    """Test the run_workflow endpoint with user ID in header"""
    # Prepare test data
    test_data = {
        "user_prompt": "Create a Python hello world script",
        "test_conditions": "Should print 'hello world'",
    }

    # Set header with user ID
    headers = {"X-User-ID": "header-user-id"}

    # Call the endpoint
    response = client.post("/run_workflow", json=test_data, headers=headers)

    # Verify response
    assert response.status_code == 200

    # Verify client was called correctly with user ID from header
    mock_client.schedule_workflow.assert_called_once()
    call_args = mock_client.schedule_workflow.call_args[1]
    assert "header-user-id" in call_args["workflow_id"]
    assert call_args["input"]["user_id"] == "header-user-id"


def test_run_workflow_anonymous(client, mock_client):
    """Test the run_workflow endpoint with no user ID (anonymous)"""
    # Prepare test data
    test_data = {
        "user_prompt": "Create a Python hello world script",
        "test_conditions": "Should print 'hello world'",
    }

    # Call the endpoint
    response = client.post("/run_workflow", json=test_data)

    # Verify response
    assert response.status_code == 200

    # Verify client was called correctly with anonymous user
    mock_client.schedule_workflow.assert_called_once()
    call_args = mock_client.schedule_workflow.call_args[1]
    assert "anonymous" in call_args["workflow_id"]
    assert call_args["input"]["user_id"] == "anonymous"


# There is no separate get_workflow_result endpoint in the API
# Results are returned directly from run_workflow


@patch("main.os.listdir")
@patch("main.os.path.isdir")
def test_list_output_dirs(mock_isdir, mock_listdir, client):
    """Test the list_output_dirs endpoint"""
    # Mock directory listing
    mock_listdir.return_value = ["final_123", "final_456", "random_dir"]
    mock_isdir.return_value = True

    # Call the endpoint
    response = client.get("/output_dirs")

    # Verify response
    assert response.status_code == 200
    assert set(response.json()) == {"final_123", "final_456"}


@patch("main.os.path.exists")
@patch("main.os.path.join")
def test_get_output_file_not_found(mock_join, mock_exists, client):
    """Test the get_output_file endpoint when file not found"""
    # Mock file existence check
    mock_exists.return_value = False
    mock_join.return_value = "/test/path"

    # Call the endpoint
    response = client.get("/output_file/test_dir/test_file.txt")

    # Verify response is 404
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]
