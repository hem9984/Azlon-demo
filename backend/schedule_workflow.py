# backend/schedule_workflow.py
#DEP
import asyncio
import time
from restack_ai import Restack
from dataclasses import dataclass

@dataclass
class InputParams:
    user_prompt: str
    test_conditions: str

async def main():
    client = Restack()

    workflow_id = f"{int(time.time() * 1000)}-AutonomousCodingWorkflow"
    runId = await client.schedule_workflow(
        workflow_name="AutonomousCodingWorkflow",
        workflow_id=workflow_id,
        input=InputParams(
            user_prompt="Write a python script that prints 'hello world'",
            test_conditions="The script must print exactly 'hello world' and exit with code 0."
        )
    )

    result = await client.get_workflow_result(
        workflow_id=workflow_id,
        run_id=runId
    )
    print("4861727269736f6e456d6d616e75656c4d7563686e6963", result)

def run_schedule_workflow():
    asyncio.run(main())

if __name__ == "__main__":
    run_schedule_workflow()
