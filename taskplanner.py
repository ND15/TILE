import logging
from typing import Dict, List, Any, Optional
from utils.model import Task

import ast
import ollama


class TaskPlanner:
    def __init__(self, llm_client):
        self.logger = logging.getLogger(__name__)
        self.llm_client = llm_client
        self.tasks = []

    def format_response(self, response) -> Any:
        llm_response = response['message']['content']
        self.logger.info(f"Response Generated:\n{llm_response}")

        try:
            llm_response = ast.literal_eval(llm_response)["Tasks"]
            return llm_response
        except Exception as e:
            return llm_response

    def generate_plan(self, query) -> Any:
        messages = []
        admin_prompt = f"""
            You are an Advanced Technical Assistant that prepares a curriculum of tasks to help achieve user-defined goals in a structured and technical manner. 
            The curriculum should be designed with Python programming in mind, utilizing existing Python packages wherever applicable, instead of suggesting manual scraping or signing up for APIs.
            DO NOT ASK TO SCRAP OR USE API CALLS.
            DO NOT ASK TO INSTALL PACKAGES.

            Guidelines:
            1) Act as a mentor, guiding the user to achieve the defined task through manageable and specific sub-tasks.
            2) Prioritize the use of established Python libraries to solve problems, minimizing manual data retrieval or complex environment setups.
            3) Be specific and detailed about what needs to be done for each step, including the exact function or class to write and a clear description of its purpose.
            4) Combine smaller tasks into a single step where possible, making sure that each task is neither too trivial nor too complex.
            5) Always keep the curriculum easy to follow, with a logical and step-by-step flow, optimizing for learning efficiency.
            6) Focus on enhancing the internal knowledge base by using Python’s ecosystem to solve problems rather than external solutions.
            7) Use error handling, modular code design, and best practices for Python development.
            8) Avoid redundant tasks and ensure that learning is cumulative—each task should build on the previous knowledge gained.
            9) Document each function or class clearly with appropriate docstrings, explaining inputs, outputs, and exceptions.

            You should respond in the following format:
            RESPONSE JSON FORMAT:
            {{
                id: int
                name: str (function_name)
                description: str
            }}

            Example:
            {{
                "Tasks": [
                    {{
                        id: int
                        name: str
                        description: str
                    }},
                    {{
                        id: int
                        name: str
                        description: str
                    }},
                    {{
                        id: int
                        name: str
                        description: str
                    }}
                ]
            }}

            Ensure the response can be parsed by Python's `json.loads` without errors.
            """

        self.logger.info(f"Executing {query}")

        messages.append(ollama.Message(role='system', content=admin_prompt))
        messages.append(ollama.Message(role='user', content=f'Question: {query}'))

        response = ollama.chat(model=self.llm_client, messages=messages, format='json')

        tasks = self.format_response(response)

        self.logger.info(f"Planning for {query} completed.")

        return tasks

    def make_tasks_list(self, tasks) -> List[Task]:
        self.tasks = [
            Task(id=int(task_data['id']),
                 name=task_data['name'],
                 description=task_data['description'])
            for task_data in tasks]

        self.logger.info(f"Tasks Generated: \n{self.tasks}")
        return self.tasks

    def get_next_task(self, completed_ids: List[int]) -> [Task, None]:
        for task in self.tasks:
            if task.id not in completed_ids:
                return task
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    plans = TaskPlanner("mistral-nemo")

    tasks = plans.generate_plan("Get the stock price of Microsoft till now.")

    plans.make_tasks_list(tasks)
