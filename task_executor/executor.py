import json
import traceback
from datetime import datetime
from dataclasses import field, dataclass
from typing import Dict, List, Optional
from prompts.prompts import TASK_DESC_PROMPT, PROMPT_TEMPLATE
from adalflow import Generator, Component, DataClassParser, DataClass, \
    JsonOutputParser, ModelClient, OpenAIClient
from context_manager import TaskContextManager, TaskAttempt


@dataclass
class Response(DataClass):
    task: str = field(metadata={"desc": "task description"})
    code: str = field(metadata={"desc": "generated code"})

    __output_fields__ = ["task", "code"]


class CodeGenerator(Component):
    def __init__(self,
                 model_client: ModelClient,
                 model_kwargs: Dict,
                 **kwargs) -> None:
        super().__init__(**kwargs)

        self.parser = DataClassParser(data_class=Response, return_data_class=True)

        self.generator = Generator(model_client=model_client,
                                   model_kwargs=model_kwargs,
                                   template=PROMPT_TEMPLATE,
                                   prompt_kwargs={
                                       "task_desc_str": TASK_DESC_PROMPT,
                                       "output_format_str": self.parser.get_output_format_str(),
                                   },
                                   output_processors=self.parser)
        
    def formatted_successful_context(successful_context: Dict[str, TaskAttempt]):
        # TODO Maybe will replace with yaml like output for formatting
        response = "".join([f"\nTask ID: {task_id}\nTask: {attempt.task}\nCode:\n{attempt.code}\n"
                             f"----------------------------------------------------------------\n"
              for task_id, attempt in successful_context.items()])

        return response

    def format_failure_history(self, failure_history: List[TaskAttempt]):
        # TODO check appending task here
        response = "".join([f"\nTask: {attempt.task}\nCode: \n{attempt.code}\nError: \n{attempt.error}\n"
                             f"------------------------------------------------\n"
              for attempt in failure_history])
        
        return response
    
    def format_previous_response(self, previous_response: TaskAttempt):
        response = f"""\n
        Task: {previous_response.task}\n
        Code: {previous_response.task}\n
        Error: {previous_response.error}\n
        """
        
        return response
        

    def call(self, task_description: str, successful_context: Dict[str, TaskAttempt],
             failure_history: List[TaskAttempt] | None, previous_response: TaskAttempt | None):
            successful_tasks = self.formatted_successful_context(successful_context)
            previous_failed_attempt = self.format_failure_history(failure_history)
            previous_attempt = self.format_previous_response(previous_response)

            try:
                response = self.generator.call(prompt_kwargs={
                    "input_str": task_description,
                    "successful_tasks": successful_tasks,
                    "previous_failed_attempt": previous_failed_attempt,
                    "previous_attempt": previous_attempt,
                })
                return response["data"]
            except Exception as e:
                return f"Error {e} getting response from generator."


class TaskExecutor(Component):
    def __init__(self, manager: TaskContextManager,
                 generator: Generator, **kwargs):
        """
        Logic for handling execution and error

        Args:
            manager: Task Context Manager class
            generator: LLM Agent
        """
        super().__init__(**kwargs)
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
