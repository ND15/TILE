from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class TaskAttempt:
    task: str = field(metadata={"desc": "task information"})
    code: str = field(metadata={"desc": "generated code"})
    timestamp: datetime = field(metadata={"desc": "timestamp for the generated code"})
    success: bool = field(metadata={"desc": "execution result"})
    error: Optional[Dict | str] = field(metadata={"desc": "error associated if any"})


class TaskContextManager:
    def __init__(self):
        """
        Class for managing and tracking successful and unsuccessful
        attempts of task execution
        """
        self.task_history: Dict[str, List[TaskAttempt]] = {}
        self.successful_tasks: Dict[str, TaskAttempt] = {}

    def add_attempt(self, task_id: str, task_attempt: TaskAttempt):
        """
        Adds task attempt to the history

        Args:
            task_id: Task ID
            task_attempt: TaskAttempt data class
        """
        if task_attempt.success:
            self.successful_tasks[task_id] = task_attempt
        else:
            if task_id not in self.task_history:
                self.task_history[task_id] = []
            self.task_history[task_id].append(task_attempt)

    def get_successful_tasks(self) -> Dict[str, TaskAttempt]:
        """
        Return:
            a dict of successfully executed code
        """
        return self.successful_tasks

    def get_attempt_history(self, task_id: str) -> list[TaskAttempt]:
        """
        Args
            task_id: Task ID

        Returns:
            All failed attempts of a particular task
        """
        return self.task_history.get(task_id, None)

    def get_last_attempt(self, task_id) -> TaskAttempt | None:
        """
        Args:
            task_id: Task ID
        Returns:
            Last attempt of a particular task
        """
        if task_id in self.task_history and self.task_history[task_id]:
            return self.task_history[task_id][-1]

        return None

    def get_successful_code(self, task_id: str) -> TaskAttempt | None:
        """
        Args:
            task_id: Task ID

        Returns:
            Attempt Information of that particular task
        """
        if task_id in self.successful_tasks:
            return self.successful_tasks[task_id]
        return None

    def get_all_successful_tasks(self) -> Dict:
        """
        Returns:
            All succesfful tasks
        """
        return self.successful_tasks.copy()

    def get_all_attempts(self, task_id) -> Dict:
        """
        Args:
            task_id: Task ID
        Returns:
            Returns both failed and success attempts
        """
        return {
            "successful": self.successful_tasks.get(task_id, []),
            "unsucessful": self.task_history.get(task_id, [])
        }
