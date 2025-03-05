# ./backend/src/memory_manager.py

# for local usage
# from mem0 import Memory
import os
from typing import Any, Dict, List, Optional, Union

from mem0 import MemoryClient

MEM0_API_KEY = os.getenv("MEM0_API_KEY")

# Configure client with cloud-compatible settings
client = MemoryClient(api_key=MEM0_API_KEY)


def search_memories(
    query: str,
    run_id: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """
    Search for relevant memories filtered by run_id and user_id and agent_id.
    """
    filters_list = []

    if run_id != None:
        filters_list.append({"run_id": run_id})
    if user_id != None:
        filters_list.append({"user_id": user_id})
    if agent_id != None:
        filters_list.append({"agent_id": agent_id})

    filters = {"AND": filters_list}

    return client.search(query=query, filters=filters, version="v2")


def add_memory(
    memory: Union[str, Dict[str, Any]],
    agent_id: str,
    run_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Add a memory to Mem0.

    Args:
        memory: The memory to add. Can be a string or a dictionary.
        agent_id: The agent ID to associate with the memory.
        run_id: Optional workflow run ID to associate with the memory.
        user_id: Optional user ID to associate with the memory.
    """
    # Convert the memory to a string if it's not already
    if isinstance(memory, dict):
        memory_str = str(memory)
    else:
        memory_str = memory
    # BUT THIS IS FINE FOR ADD MEMORY
    # Prepare parameters for the add call
    params = {"agent_id": agent_id}
    if run_id != None:
        params["run_id"] = run_id
    if user_id != None:
        params["user_id"] = user_id

    return client.add(messages=memory_str, **params)


def get_all_memories(
    agent_id: str, run_id: Optional[str] = None, user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all memories from Mem0.

    Args:
        agent_id: The agent ID to retrieve memories for.
        run_id: Optional workflow run ID to filter memories by.
        user_id: Optional user ID to filter memories by.

    Returns:
        A list of memory items compatible with the MemoryItem schema.
    """
    # Prepare filters for v2 API
    # Build filters list with required and optional filters
    filter_list = []

    # Always add agent_id filter
    filter_list.append({"agent_id": agent_id})

    # Add run_id filter only if provided
    if run_id is not None:
        filter_list.append({"run_id": run_id})

    # Add user_id filter only if provided
    if user_id is not None:
        filter_list.append({"user_id": user_id})

    # Construct the final filters object
    filters = {"AND": filter_list}
    # Use v2 API to get memories
    response = client.get_all(version="v2", filters=filters)
    # Format memories to match the MemoryItem schema
    formatted_memories = []

    # Check if response has memories
    if isinstance(response, dict) and response.get("memories") is not None:
        raw_memories = response.get("memories")
    else:
        # If not, assume the response itself is the list of memories
        raw_memories = response

    if raw_memories and isinstance(raw_memories, list):
        for memory in raw_memories:
            if isinstance(memory, dict):
                # If memory has a 'memory' field (per v2 API), use that as content
                if "memory" in memory:
                    formatted_memories.append({"content": memory["memory"]})
                # If the memory already has a 'content' field, use it directly
                elif "content" in memory:
                    formatted_memories.append(memory)
                else:
                    # Otherwise just use the whole memory object as content
                    formatted_memories.append({"content": str(memory)})
            else:
                # If memory is not a dict, wrap it in a dict with a 'content' field
                formatted_memories.append({"content": str(memory)})

    return formatted_memories


# WRONG WAY TO DO IT
def get_all_memories_top_5(agent_id, run_id=None, user_id=None):
    """
    Get top 5 memories from Mem0.

    Args:
        agent_id: The agent ID to retrieve memories for.
        run_id: Optional workflow run ID to filter memories by.
        user_id: Optional user ID to filter memories by.

    Returns:
        A list of memory items compatible with the MemoryItem schema.
    """
    # Prepare filters for v2 API
    filters = {}
    if agent_id is not None:
        filters["agent_id"] = agent_id
    if run_id is not None:
        filters["run_id"] = run_id
    if user_id is not None:
        filters["user_id"] = user_id

    # Use v2 API to get memories with top_k=5
    response = client.get_all(version="v2", filters=filters, top_k=5)

    # Format memories to match the MemoryItem schema
    formatted_memories = []

    # Check if response has memories
    if isinstance(response, dict) and response.get("memories") is not None:
        raw_memories = response.get("memories")
    else:
        # If not, assume the response itself is the list of memories
        raw_memories = response

    if raw_memories and isinstance(raw_memories, list):
        for memory in raw_memories:
            if isinstance(memory, dict):
                # If memory has a 'memory' field (per v2 API), use that as content
                if "memory" in memory:
                    formatted_memories.append({"content": memory["memory"]})
                # If the memory already has a 'content' field, use it directly
                elif "content" in memory:
                    formatted_memories.append(memory)
                else:
                    # Otherwise just use the whole memory object as content
                    formatted_memories.append({"content": str(memory)})
            else:
                # If memory is not a dict, wrap it in a dict with a 'content' field
                formatted_memories.append({"content": str(memory)})

    return formatted_memories
