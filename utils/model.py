from datetime import datetime
from typing import List, Dict, Literal, Any, Optional
from dataclasses import dataclass
import ast
import traceback
import ollama

TASK_STATUS = Literal["pending", "in_progress", "failed", "completed"]
EXECUTION_STATUS = Literal["success", "failure"]
MessageRole = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: MessageRole
    content: str
    images = None


@dataclass
class Response:
    task: str
    response: str


@dataclass
class Task:
    id: int
    name: str
    description: str
    status: TASK_STATUS = 'pending'
    task_feedbacks = []
    max_retries: int = 3
    retry_count: int = 0
    task_count: int = 0
    task_tracker = {'previous_tasks': [], 'original_query': '', 'responses': ''}


@dataclass
class Function:
    pass


@dataclass
class ExecutionResult:
    status: EXECUTION_STATUS
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class Skill:
    name: str
    description: str
    code: str
    package_dependencies: List[str]
    function_dependencies: List[str]
    created_at: datetime
    success_count: int = 0
    failure_count: int = 0
    average_execution_time: float = 0.0
    tags: List[str] = None
