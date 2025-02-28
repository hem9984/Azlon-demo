"""
Tests for memory_manager module.
"""
import pytest
from unittest.mock import patch, MagicMock
import json
from src.memory_manager import get_all_memories, add_memory


@pytest.fixture
def mock_memory_client():
    """Fixture to mock the MemoryClient."""
    with patch('src.memory_manager.client') as mock_client:
        yield mock_client


def test_get_all_memories_empty(mock_memory_client):
    """Test get_all_memories with empty response."""
    mock_memory_client.get_all.return_value = []
    result = get_all_memories('test_agent')
    
    mock_memory_client.get_all.assert_called_once_with(agent_id='test_agent')
    assert result == []


def test_get_all_memories_with_content(mock_memory_client):
    """Test get_all_memories with content field."""
    mock_memory_client.get_all.return_value = [{'content': 'memory1'}, {'content': 'memory2'}]
    result = get_all_memories('test_agent')
    
    mock_memory_client.get_all.assert_called_once_with(agent_id='test_agent')
    assert result == [{'content': 'memory1'}, {'content': 'memory2'}]


def test_get_all_memories_without_content(mock_memory_client):
    """Test get_all_memories with non-dict memories."""
    mock_memory_client.get_all.return_value = ['memory1', 'memory2']
    result = get_all_memories('test_agent')
    
    mock_memory_client.get_all.assert_called_once_with(agent_id='test_agent')
    assert result == [{'content': 'memory1'}, {'content': 'memory2'}]


def test_get_all_memories_mixed_types(mock_memory_client):
    """Test get_all_memories with mixed memory types."""
    mock_memory_client.get_all.return_value = ['memory1', {'content': 'memory2'}, {'other_field': 'value'}]
    result = get_all_memories('test_agent')
    
    mock_memory_client.get_all.assert_called_once_with(agent_id='test_agent')
    assert result == [{'content': 'memory1'}, {'content': 'memory2'}, {'content': "{'other_field': 'value'}"}]


def test_get_all_memories_none(mock_memory_client):
    """Test get_all_memories with None response."""
    mock_memory_client.get_all.return_value = None
    result = get_all_memories('test_agent')
    
    mock_memory_client.get_all.assert_called_once_with(agent_id='test_agent')
    assert result == []


def test_add_memory_string(mock_memory_client):
    """Test add_memory with string input."""
    memory = "test memory string"
    add_memory(memory, 'test_agent')
    
    mock_memory_client.add.assert_called_once_with(messages=memory, agent_id='test_agent')


def test_add_memory_dict(mock_memory_client):
    """Test add_memory with dict input."""
    memory = {"key": "value"}
    add_memory(memory, 'test_agent')
    
    # Check if json.dumps was used to convert dict to string
    mock_memory_client.add.assert_called_once_with(messages=json.dumps(memory), agent_id='test_agent')


def test_add_memory_complex_object(mock_memory_client):
    """Test add_memory with complex object input that cannot be JSON serialized."""
    class ComplexObject:
        def __str__(self):
            return "complex object string representation"
    
    memory = ComplexObject()
    add_memory(memory, 'test_agent')
    
    mock_memory_client.add.assert_called_once_with(messages=str(memory), agent_id='test_agent')
