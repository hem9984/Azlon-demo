from mem0 import MemoryClient
# for local usage
#from mem0 import Memory
import os

MEM0_API_KEY = os.getenv('MEM0_API_KEY')

client = MemoryClient(api_key=MEM0_API_KEY)

def search_memories(query, run_id=None, user_id=None, agent_id=None):
    """
    Search for relevant memories filtered by run_id and user_id and agent_id.
    """
    filters = {}
    
    if run_id:
        filters["run_id"] = run_id
    if user_id:
        filters["user_id"] = user_id
    if agent_id:
        filters["agent_id"] = agent_id
        
    return client.search(query=query, filters=filters, version="v2")

def add_memory(memory, agent_id, run_id=None, user_id=None):
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
    
    # Prepare parameters for the add call
    params = {"agent_id": agent_id}
    if run_id:
        params["run_id"] = run_id
    if user_id:
        params["user_id"] = user_id
        
    return client.add(messages=memory_str, **params)

def get_all_memories(agent_id, run_id=None, user_id=None):
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
    filters = {}
    if agent_id:
        filters["agent_id"] = agent_id
    if run_id:
        filters["run_id"] = run_id
    if user_id:
        filters["user_id"] = user_id
    
    # Use v2 API to get memories
    response = client.get_all(version="v2", filters=filters)
    
    # Format memories to match the MemoryItem schema
    formatted_memories = []
    
    # Check if response has memories
    if isinstance(response, dict) and response.get('memories') is not None:
        raw_memories = response.get('memories')
    else:
        # If not, assume the response itself is the list of memories
        raw_memories = response
    
    if raw_memories and isinstance(raw_memories, list):
        for memory in raw_memories:
            if isinstance(memory, dict):
                # If memory has a 'memory' field (per v2 API), use that as content
                if 'memory' in memory:
                    formatted_memories.append({'content': memory['memory']})
                # If the memory already has a 'content' field, use it directly
                elif 'content' in memory:
                    formatted_memories.append(memory)
                else:
                    # Otherwise just use the whole memory object as content
                    formatted_memories.append({'content': str(memory)})
            else:
                # If memory is not a dict, wrap it in a dict with a 'content' field
                formatted_memories.append({'content': str(memory)})
    
    return formatted_memories

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
    if agent_id:
        filters["agent_id"] = agent_id
    if run_id:
        filters["run_id"] = run_id
    if user_id:
        filters["user_id"] = user_id
    
    # Use v2 API to get memories with top_k=5
    response = client.get_all(version="v2", filters=filters, top_k=5)
    
    # Format memories to match the MemoryItem schema
    formatted_memories = []
    
    # Check if response has memories
    if isinstance(response, dict) and response.get('memories') is not None:
        raw_memories = response.get('memories')
    else:
        # If not, assume the response itself is the list of memories
        raw_memories = response
    
    if raw_memories and isinstance(raw_memories, list):
        for memory in raw_memories:
            if isinstance(memory, dict):
                # If memory has a 'memory' field (per v2 API), use that as content
                if 'memory' in memory:
                    formatted_memories.append({'content': memory['memory']})
                # If the memory already has a 'content' field, use it directly
                elif 'content' in memory:
                    formatted_memories.append(memory)
                else:
                    # Otherwise just use the whole memory object as content
                    formatted_memories.append({'content': str(memory)})
            else:
                # If memory is not a dict, wrap it in a dict with a 'content' field
                formatted_memories.append({'content': str(memory)})
    
    return formatted_memories