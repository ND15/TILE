import json
import traceback
from datetime import datetime
from dataclasses import field, dataclass
from typing import Dict

from adalflow import Generator, Component, DataClassParser, DataClass
from context_manager import TaskContextManager, TaskAttempt


@dataclass
class Response(DataClass):
    task: str = field(metadata={"desc": "task description"})
    code: str = field(metadata={"desc": "generated code"})

    __output_fields__ = ["task", "code"]


class TaskExecutor(Component):
    def __init__(self, manager: TaskContextManager,
                 generator: Generator):
        """
        Logic for handling execution and error

        Args:
            manager: Task Context Manager class
            generator: LLM Agent
        """
        super().__init__()
        self.context_manager = manager
        self.generator = generator

    # currently no limit on retries
    def execute_task_with_reties(self, task_id: str, task_description: str):
        while True:
            successful_context = self.context_manager.get_successful_tasks()
            failure_history = self.context_manager.get_attempt_history(task_id=task_id)
            previous_response = self.context_manager.get_last_attempt(task_id=task_id)

            llm_response = self.generator.generate_response(
                task_description=task_description,
                successful_context=successful_context,
                failure_history=failure_history,
                previous_response=previous_response
            )

            response = self.format_response(llm_response)

            if isinstance(response, dict):
                error_message = {
                    'type': type(e).__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }

                task_attempt = TaskAttempt(
                    task=task_description,
                    code=None,
                    timestamp=datetime.now(),
                    success=False,
                    error=error_message
                )

                self.context_manager.add_attempt(
                    task_id=task_id,
                    task_attempt=task_attempt
                )

                continue

            try:
                self.execute_code(response)

                task_attempt = TaskAttempt(
                    task=task_description,
                    code=response,
                    timestamp=datetime.now(),
                    success=True,
                    error=None
                )

                self.context_manager.add_attempt(
                    task_id=task_id,
                    task_attempt=task_attempt
                )

            except Exception as e:
                error_message = {
                    'type': type(e).__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }

                task_attempt = TaskAttempt(
                    task=task_description,
                    code=response,
                    timestamp=datetime.now(),
                    success=False,
                    error=error_message
                )

                self.context_manager.add_attempt(
                    task_id=task_id,
                    task_attempt=task_attempt
                )

    def format_response(self, llm_response: str) -> str:
        llm_response = str(llm_response)
        llm_response = llm_response.strip()

        try:
            start = llm_response.find('{')
            end = llm_response.rfind('}')

            text = llm_response[start:end + 1] if start != -1 and end != -1 else None
            response = json.loads(text)["code"]
            self.logger.info(f"Response Generated Parser:\n{response}")
            return response

        except Exception as e:
            self.logger.info(llm_response)
            self.logger.error(f"Error occured while parsing, Error {e}")

    def execute_code(self, response: str):
        exec(response, locals())
        