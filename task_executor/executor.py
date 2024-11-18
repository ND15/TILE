import ast
import logging
import sys
import os
import time

sys.path.append(os.getcwd())

import json
import traceback
from datetime import datetime
from dataclasses import field, dataclass
from typing import Dict, List, Any
from prompts.prompts import ACTION_TASK_DESC_PROMPT, PROMPT_TEMPLATE
from adalflow import Generator, Component, DataClassParser, DataClass, ModelClient, OllamaClient, JsonOutputParser
from context_manager import TaskContextManager, TaskAttempt
from task_planner.planner import TaskInfo
from adalflow.utils.logger import printc


@dataclass
class Response(DataClass):
    task: str = field(metadata={"desc": "task description"})
    code: str = field(metadata={"desc": "generated code should be enclosed within triple double-quotes"})

    __output_fields__ = ["task", "code"]


class CodeGenerator(Component):
    def __init__(self,
                 model_client: ModelClient,
                 model_kwargs: Dict) -> None:
        super().__init__()
        self.parser = DataClassParser(data_class=Response, return_data_class=True)

        self.code_generator = Generator(model_client=model_client,
                                        model_kwargs=model_kwargs,
                                        template=PROMPT_TEMPLATE,
                                        prompt_kwargs={
                                            "task_desc_str": ACTION_TASK_DESC_PROMPT,
                                            "output_format_str": self.parser.get_output_format_str(),
                                        })

    @staticmethod
    def formatted_successful_context(successful_context: Dict[str, TaskAttempt]):
        # TODO Maybe will replace with yaml like output for formatting
        response = "".join([f"\nTask ID: {task_id}\nTask: {attempt.task}\nCode:\n{attempt.code}\n"
                            f"----------------------------------------------------------------\n"
                            for task_id, attempt in successful_context.items()])

        return response

    @staticmethod
    def format_failure_history(failure_history: List[TaskAttempt]):
        # TODO check appending task here
        response = "".join([f"\nTask: {attempt.task}\nCode: \n{attempt.code}\nError: \n{attempt.error}\n"
                            f"------------------------------------------------\n"
                            for attempt in failure_history])

        return response

    @staticmethod
    def format_previous_response(previous_response: TaskAttempt):
        response = f"""\n
        Task: {previous_response.task}\n
        Code: {previous_response.task}\n
        Error: {previous_response.error}\n
        """

        return response

    def call(self, task_description: str, successful_context: Dict[str, TaskAttempt] | None,
             failure_history: List[TaskAttempt] | None, previous_response: TaskAttempt | None):
        if successful_context:
            successful_tasks = self.formatted_successful_context(successful_context)
        else:
            successful_tasks = None

        if failure_history:
            previous_failed_attempt = self.format_failure_history(failure_history)
        else:
            previous_failed_attempt = None

        if previous_response:
            previous_attempt = self.format_previous_response(previous_response)
        else:
            previous_attempt = None

        printc("*" * 100, color='yellow')
        printc(f"Task Description:\n{task_description}", color='yellow')
        printc(f"Successful Tasks:\n{successful_tasks}", color='yellow')
        printc(f"Fail History:\n{previous_failed_attempt}", color='yellow')
        printc(f"Previous Response:\n{previous_attempt}", color='yellow')
        printc("*" * 100, color='yellow')

        time.sleep(3)
        try:
            response = self.code_generator.call(prompt_kwargs={
                "input_str": task_description,
                "successful_tasks": successful_tasks,
                "previous_failed_attempt": previous_failed_attempt,
                "previous_attempt": previous_attempt,
            })
            # printc(f"Response from code generator: {response.data}", color="yellow")
            return response.data
        except Exception as e:
            printc(f"Error {e} getting response from generator.", color="red")
            return e


class TaskExecutor(Component):
    def __init__(self, manager: TaskContextManager,
                 generator: CodeGenerator):
        """
        Logic for handling execution and error

        Args:
            manager: Task Context Manager class
            generator: LLM Agent
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.context_manager = manager
        self.code_generator = generator

    # currently no limit on retries
    def execute_task_with_reties(self, task_id: str, task_description: str):
        while True:
            successful_context = self.context_manager.get_successful_tasks()
            failure_history = self.context_manager.get_attempt_history(task_id=task_id)
            previous_response = self.context_manager.get_last_attempt(task_id=task_id)

            llm_response = self.code_generator.call(
                task_description=task_description,
                successful_context=successful_context,
                failure_history=failure_history,
                previous_response=previous_response
            )

            response = self.format_response(llm_response)

            if isinstance(response, dict):
                task_attempt = TaskAttempt(
                    task=task_description,
                    code=str(response),
                    timestamp=datetime.now(),
                    success=False,
                    error=response
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

                return task_attempt

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

    @staticmethod
    def format_response(llm_response: str | object) -> dict[str, str] | Any:
        llm_response = str(llm_response)
        llm_response = llm_response.strip()

        try:
            start = llm_response.find('{')
            end = llm_response.rfind('}')

            text = llm_response[start:end + 1] if start != -1 and end != -1 else None
            response = ast.literal_eval(str(text))["code"]
            printc(f"Response Generated Parser:\n{response}", color="green")
            return response

        except Exception as e:
            printc(llm_response, color="yellow")
            printc(f"Error occured while parsing, Error {e}", color="red")
            return {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }

    @staticmethod
    def execute_code(response: str):
        printc("EXECUTING CODE", color="magenta")
        exec(response, globals())  # TODO this can be an issue


if __name__ == "__main__":
    tasks = [TaskInfo(id=1, name='Define a function to load historical stock data from yfinance library',
                      description='This task involves defining a function that uses the yfinance library to load the historical price data of a given stock.',
                      dependencies=[]),
             TaskInfo(id=2,
                      name='Implement a function to calculate Simple Moving Averages (SMA) from the historical data',
                      description='This task requires implementing a function that calculates the Simple Moving Average (SMA) for a given window size using the historical data.',
                      dependencies=[1]), TaskInfo(id=3,
                                                  name='Create a function to calculate Exponential Moving Averages (EMA) from the historical data',
                                                  description='This task involves defining a function that calculates the Exponential Moving Average (EMA) for a given window size using the historical data.',
                                                  dependencies=[1]),
             TaskInfo(id=4,
                      name='Develop a function to calculate Relative Strength Index (RSI) from the historical data',
                      description='This task requires implementing a function that calculates the Relative Strength Index (RSI) for a given window size using the historical data.',
                      dependencies=[1]),
             TaskInfo(id=5, name='Create a function to calculate Bollinger Bands from the historical data',
                      description='This task involves defining a function that calculates the Bollinger Bands for a given window size using the historical data.',
                      dependencies=[1, 2]),
             TaskInfo(id=6, name='Combine the indicators into a single function to calculate multiple indicators',
                      description='This task requires combining the functions from previous tasks into a single function that calculates multiple indicators for a given stock.',
                      dependencies=[1, 2, 3, 4, 5])]

    code_generator = CodeGenerator(model_client=OllamaClient(),
                                   model_kwargs={
                                       "model": "mistral-nemo:latest",
                                       "stream": False})

    context_manager = TaskContextManager()

    task_executor = TaskExecutor(manager=context_manager, generator=code_generator)

    task_executor.execute_task_with_reties(task_id="1", task_description=tasks[0].name)
