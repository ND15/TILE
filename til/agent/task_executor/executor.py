import ast
import os
import sys

sys.path.append(os.getcwd())

import logging
import time
import traceback
from dataclasses import field, dataclass
from datetime import datetime
from typing import Dict, List
from til.prompts.prompts import ACTION_TASK_DESC_PROMPT
from adalflow import Component, DataClass, setup_env
from context_manager import TaskContextManager, TaskAttempt
from adalflow.utils.logger import printc
from til.agent.task_executor.base import ExecutionResult, Task
from til.agent.task_executor.reflection import Reflection
from til.chat.base import Message
from til.chat.model import GeminiModel, OllamaModel, OpenaiModel, OpenRouter

setup_env("til/configs/.env")


@dataclass
class Response:
    task: str
    response: str


@dataclass
class ActionResponse(DataClass):
    task: str = field(metadata={"desc": "description of the task"})
    code: str = field(metadata={"desc": "generated code response"})

    __output_fields__ = ["task", "code"]


class CodeGenerator:
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def formatted_successful_context(successful_context: Dict[str, TaskAttempt]):
        # TODO Maybe will replace with yaml like output for formatting
        response = "You have successfully completed and executed these tasks. Use can refer and call them wherever necessary.\n"
        response += "".join([f"\nTask ID: {task_id}\nTask: {attempt.task}\nCode:\n{attempt.code}\n"
                             f"----------------------------------------------------------------\n"
                             for task_id, attempt in successful_context.items()])

        return response

    @staticmethod
    def format_failure_history(failure_history: List[TaskAttempt]):
        # TODO check appending task here
        response = "For the current task, these are your attempts that have felt.\n"
        response += "".join([f"\nTask: {attempt.task}\nCode: \n{attempt.code}\nError: \n{attempt.error}\n"
                             f"------------------------------------------------\n"
                             for attempt in failure_history])

        return response

    @staticmethod
    def format_previous_response(previous_response: TaskAttempt):
        response = "You previous response: \n"
        response += f"""\n
        Task: {previous_response.task}\n
        Code: {previous_response.code}\n
        Error: {previous_response.error}\n
        """

        return response


class TaskExecutor(Component):
    def __init__(self, config: Dict, context_manager: TaskContextManager,
                 generator: CodeGenerator):
        super().__init__()
        self.context_manager = context_manager
        self.code_generator = generator
        self.flag = 0
        self.config = config

        match self.config.get("model_type"):
            case "gemini":
                self.chat_model = GeminiModel(model_config=self.config)
            case "openai":
                self.chat_model = OpenaiModel(model_config=self.config)
            case "openrouter":
                self.chat_model = OpenRouter(model_config=self.config)
            case "ollama":
                self.chat_model = OllamaModel(model_config=self.config)

        self.completed_tasks = []

    @staticmethod
    def format_response(llm_response) -> str | Dict:
        try:
            if "```json" in llm_response:
                llm_response = llm_response.strip()

                if llm_response.startswith('```json'):
                    llm_response = llm_response[7:]
                if llm_response.endswith('```'):
                    llm_response = llm_response[:-3]

            start = llm_response.find('{')
            end = llm_response.rfind('}')

            text = llm_response[start:end + 1] if start != -1 and end != -1 else None
            response = ast.literal_eval(text)["code"]
            printc(f"Response Generated Parser:\n{response}", color="green")
            return response

        except Exception as e:
            printc(f"Error occured while parsing, Error {e}", color="red")
            printc(f"Errored Response: \n{llm_response}", color="red")
            return {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }

    def generate_and_execute_new_task(self, task: Task):
        if self.flag == 0:
            self.chat_model.check_system_prompt(system_prompt=ACTION_TASK_DESC_PROMPT)
            self.flag += 1

        self.chat_model.add_message(Message(role="user",
                                            content=f"{self.code_generator.formatted_successful_context(self.context_manager.get_successful_tasks())}"))

        if task.feedbacks:
            failed_history = self.context_manager.get_attempt_history(str(task.id))

            if failed_history:
                failed_history = self.code_generator.format_failure_history(failed_history)

            previous_response = self.context_manager.get_last_attempt(str(task.id))

            if previous_response:
                previous_attempt = self.code_generator.format_previous_response(previous_response)
                self.chat_model.add_message(Message(role="user", content=failed_history))

            self.chat_model.add_message(Message(role="user", content=f"Feedback for the error in your previous response"
                                                                     f"{task.feedbacks[-1]}"))

            llm_response = self.chat_model.chat(
                f"Current Task: {task.description}. Keep in mind your previous response and rectify the errors.")

        else:
            llm_response = self.chat_model.chat(f"Current Task: {task.description}")

        code_response = self.format_response(llm_response.content)

        if isinstance(code_response, dict):
            task_attempt = TaskAttempt(
                task=task.name,
                code=str(code_response),
                timestamp=datetime.now(),
                success=False,
                error="Error in parsing the output. The generated response didn't follow the output format specified"
            )

            self.context_manager.add_attempt(
                task_id=str(task.id),
                task_attempt=task_attempt
            )

            return ExecutionResult(status="failure", output="error")

        task_attempt = TaskAttempt(
            task=task.name,
            code=code_response,
            timestamp=datetime.now(),
            success=False,
            error=None
        )

        time.sleep(15)

        if code_response:
            try:
                exec(code_response, globals())
                task_attempt.success = True
                self.context_manager.add_attempt(str(task.id), task_attempt)
                return ExecutionResult(status="success", output=code_response)
            except Exception as e:
                error_message = {
                    'type': type(e).__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }
                task_attempt.success = False
                task_attempt.error = str(error_message)
                self.context_manager.add_attempt(str(task.id), task_attempt)
                return ExecutionResult(status='failure', output=code_response, error=error_message)

    def execute_single_task(self, task: Task) -> ExecutionResult:
        printc(f"EXECUTING TASK: {task.name}", color="magenta")
        result = self.generate_and_execute_new_task(task)
        return result

    def execute_task_with_retry_mechanism(self, task: Task, status='failure'):
        result = ExecutionResult(status='failure', output=None)
        while status != 'success':
            result = self.execute_single_task(task)

            if result.status == 'success':
                task.feedbacks = None
                return result

            task.retry_count += 1

            printc(f"Task {task.name} failed, attempt {task.retry_count}. Error: {result.error}", color="yellow")

            task.feedbacks.append(Reflection('mistral-nemo:latest').feedback_with_reflection(task, result))

        return result

    def execute_task_list(self, tasks: List[Task]) -> dict:
        results = []

        for task in tasks:
            result = self.execute_task_with_retry_mechanism(task)

            printc(f"Task - ID: {task.id}, Name: {task.name} completed successfully", color="magenta")

        printc(f"All tasks completed successfully", color="green")

        history = "\n__________\n".join([hist.content for hist in self.chat_model.conversation_history])

        print(history)

        return self.context_manager.get_all_successful_tasks()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    tasks = [Task(id=1, name='Import Necessary Libraries',
                  description='Import the required libraries: Matplotlib, NumPy, and mpl_toolkits.',
                  retry_count=0),
             Task(id=2, name='Define Emoji Face Parameters',
                  description='Define parameters for the emoji face like eye positions, smile curve points, etc.',
                  retry_count=0,
                  ),
             Task(id=3, name='Create Eye Plots',
                  description='Plot the eyes using black dots and their coordinates.',
                  retry_count=0),
             Task(id=4, name='Create Mouth Plot',
                  description='Define points for the smile curve and plot it as a line.',
                  retry_count=0),
             Task(id=5, name='Create Face Sphere',
                  description="Generate a yellow sphere to represent the face using NumPy's array functions.",
                  retry_count=0),
             Task(id=6, name='Combine All Plots into One Figure',
                  description="Combine all plots (eyes, mouth, and face) into a single 3D figure using Matplotlib's pyplot.",
                  retry_count=0),
             Task(id=7, name='Hide Axis Labels', description='Hide the axis labels for the final plot.',
                  retry_count=0)
             ]

    config = {
        "model_type": "openrouter",
        "model_name": "meta-llama/llama-3.1-70b-instruct:free",
        "generation_config":
            {
                "top_a": 0.8
            }
    }

    code_generator = CodeGenerator()

    context_manager = TaskContextManager()

    executor = TaskExecutor(config=config, context_manager=context_manager, generator=code_generator)

    executor.execute_task_list(tasks)
