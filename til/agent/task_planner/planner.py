import json
import traceback
from dataclasses import dataclass, field
from typing import List, Any, Dict
from adalflow import Component, ModelClient, Generator, DataClass, DataClassParser, setup_env
from task_planner.dependency_manager import DependencyManager, Task
from prompts.prompts import PLANNER_TASK_DESC_PROMPT, PROMPT_TEMPLATE
from til.chat.open_router import OpenAIClient

setup_env("../configs/.env")


@dataclass
class TaskInfo:
    id: int = field(metadata={"desc": "task ID"})
    name: str = field(metadata={"desc": "name of the task"})
    description: str = field(metadata={"desc": "description of the task"})  # TODO maybe thought process
    dependencies: list = field(
        metadata={"desc": "list of dependencies // List of task IDs that must be completed before this task"})


@dataclass
class PlannerResponse(DataClass):
    Tasks: List[TaskInfo] = field(metadata={"desc": "List of tasks"})

    __output_fields__ = ["Tasks"]


class TaskPlanner(Component):
    def __init__(self, model_client: ModelClient,
                 model_kwargs: Dict, **kwargs):
        super().__init__(**kwargs)
        self.task_graph = DependencyManager()

        self.parser = DataClassParser(data_class=PlannerResponse, return_data_class=True)

        self.generator = Generator(model_client=model_client,
                                   model_kwargs=model_kwargs,
                                   template=PROMPT_TEMPLATE,
                                   prompt_kwargs={
                                       "output_format_str": self.parser.get_output_format_str(),
                                       "task_desc_str": PLANNER_TASK_DESC_PROMPT
                                   })

    @staticmethod
    def format_response(llm_response: str) -> dict[str, str] | List[Dict[str, Any]]:
        llm_response = str(llm_response)
        llm_response = llm_response.strip()

        try:
            start = llm_response.find('{')
            end = llm_response.rfind('}')

            text = llm_response[start:end + 1] if start != -1 and end != -1 else None
            response = json.loads(str(text))["tasks"]
            return response

        except Exception as e:
            return {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }

    def call(self, input_str, **kwargs):
        response = self.generator.call(prompt_kwargs={
            "input_str": f"Generate Curriculum for task: {input_str}"
        }).to_dict()['data']

        print(response)

        tasks = self.format_response(response)

        for task_data in tasks:
            task = Task(
                id=int(task_data['id']),
                name=task_data['name'],
                description=task_data['description']
            )
            dependencies = task_data.get('dependencies', [])
            self.task_graph.add_task(task, dependencies)

        return self.task_graph.execution_graph()

    def get_next_task(self, completed_ids: List[int]) -> Task | None:
        for task_id in completed_ids:
            self.task_graph.mark_task(task_id=task_id, flag="completed")

        available_tasks = self.task_graph.get_available_tasks()
        return available_tasks[0] if available_tasks else None


if __name__ == "__main__":
    planner = TaskPlanner(model_client=OpenAIClient(),
                          model_kwargs={"model": "meta-llama/llama-3.1-70b-instruct:free",
                                        "stream": False})

    print(planner)

    response = planner.call(
        input_str="Generate a script for calculating different indicators of a stock from its historical price data using yfinance python library")
    print(response)
