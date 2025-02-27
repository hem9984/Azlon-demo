from mem0 import MemoryClient
# for local usage
#from mem0 import Memory
import os

MEM0_API_KEY = os.getenv('MEM0_API_KEY')

# config = {
#     "llm": {
#         "provider": "openai",
#         "config": {
#             "model": "gpt-4o",
#             "temperature": 0.2,
#             "max_tokens": 1500,
#         }
#     },
#     "custom_prompt": custom_prompt,
#     "version": "v1.1"
# }

# m = Memory.from_config(config_dict=config, user_id="alice")
client = MemoryClient(api_key=MEM0_API_KEY)

def get_all_memories(agent_id):
    """
    Get all memories from Mem0.
    """
    return client.get_all(agent_id=agent_id)

def add_memory(memory, agent_id):
    """
    Add a memory to Mem0.
    """
    return client.add(memory, agent_id=agent_id)