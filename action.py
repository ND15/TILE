from utils.model import ExecutionResult, Task, Response
from typing import List
import logging
import ast
import traceback
import ollama

from reflection import Reflection


class TaskExecutor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model = "qwen2.5-coder:7b-instruct-q6_K"
        self.completed_tasks = []

    @staticmethod
    def _generate_admin_prompt(task: Task):
        # Need to replace the response format
        admin_prompt = f"""
            You are a coding assistant that generates code to achieve a task. Your task is to return only the code. 
            The ultimate goal is to achieve the current task based on the user's original goal. Adhere to the output response at all times.

            I will be giving you the tasks one by one. And you have to write and simultaneously organize each piece of the previous code.

            You must follow the following criteria:
            - Your task is to write meaningful and executable code like a skilled python developer. The code has to be in the form of functions or classes.
            - Your functions and classes should be reusable and modular such that other functions or classes can easily use them.
            - Be very specific about what functions, classes, or optimizations.
            - Do not make simple and silly mistakes.
            - Avoid redundant or repetitive tasks.
            - You should be able to use previously generated code.
            - Do scraping only if no other option is there, otherwise try to use Python's packages.
            - Go step by step, solve each task carefully and test it.
            - Write the __main__ function for checking each generated code.

            You should only respond in the following format:
            json
            {{"code": "generated python code"}}

            RESPONSE FORMAT:
            Question: Based on the information I listed above, generate the code.
            Answer: 
            json
                {{"code": ""}}.

            Ensure the response {{"code": ""}} can be parsed by Python `json.loads`.
        """

        return admin_prompt

    # if we cant format response, call execute again
    def format_response(self, response):
        try:
            llm_response = ast.literal_eval(response['message']['content'].rstrip())['code']
            return llm_response
        except Exception as e:
            self.logger.error(f"Error parsing response: {e}")
            self.logger.info(f"Response from LLM: {response}")
            return response['message']['content']

    def generate_and_execute_new_task(self, task: Task):
        messages = [ollama.Message(role='system', content=self._generate_admin_prompt(task))]

        # TODO Bug
        """
        In previous tasks, as each task is independent, 
        I need to flow the information of previous tasks to each Task object
        putting it as a chat would explode the context winodw
        """

        if task.retry_count > 0:
            self.logger.info(f"List of completed task: {str(self.completed_tasks)}")
            messages.append(
                ollama.Message(role='assistant',
                               content=f'List of completed tasks: {str(self.completed_tasks)}'))

        if task.task_feedbacks:
            messages.append(
                ollama.Message(role='user',
                               content=f"The main goal is: {task.task_tracker['original_query']}, The current task: {task.name}"
                                       f"Feedback: {task.task_feedbacks}"))
        else:
            messages.append(
                ollama.Message(role='user',
                               content=f"The main goal is: {task.task_tracker['original_query']}, The current task: {task.name}"))

        response = ollama.chat(model=self.model,
                               messages=messages,
                               format='json')
        response = self.format_response(response)

        if response:
            try:
                exec(response, locals())
                self.completed_tasks.append(response)
                return ExecutionResult(status='success', output=response)
            except Exception as e:
                error_message = traceback.format_exc()
                return ExecutionResult(status='failure', output=response, error=error_message)

        else:
            return ExecutionResult(status='failure', output=response, error="No response generated")

    def execute_single_task(self, task: Task):
        self.logger.info(f"Executing task: {task.name}")

        result = self.generate_and_execute_new_task(task)

        return result

    def execute_task_with_retry_mechanism(self, task, status='failure'):
        result = ExecutionResult(status='failure', output=None)
        while status != 'success':
            result = self.execute_single_task(task)

            if result.status == 'success':
                task.task_feedbacks = None
                return result

            task.retry_count += 1

            self.logger.warning(f"Task {task.name} failed, attempt {task.retry_count} "
                                f"of {task.max_retries}. Error: {result.error}")

            task.task_feedbacks.append(Reflection('mistral-nemo').feedback_with_reflection(task, result))

        return result

    def execute_task_list(self, tasks: List[Task]) -> List[Response]:
        results = []

        # TODO the previously completed tasks are not propagating properly
        for task in tasks:
            result = self.execute_task_with_retry_mechanism(task)

            results.append(Response(task.name, response=result.output))

            self.logger.info(f"Task {task.name} is completed successfully.")
            self.logger.info(f"Response Generated {result.output}")

        self.logger.info(f"Tasks completed successfully.")
        return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    tasks = [
        Task(
            id=1,
            name="find_length_of_string",
            description="Calculate length of a string",
            status='pending'
        ),
        Task(
            id=2,
            name="format_greeting",
            description="Format a greeting message for Alice",
            status='pending'
        )
    ]

    executor = TaskExecutor()

    executor.execute_task_list(tasks)
