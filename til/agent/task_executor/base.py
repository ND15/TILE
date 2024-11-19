from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal

EXECUTION_STATUS = Literal["success", "failure"]


@dataclass
class ExecutionResult:
    status: EXECUTION_STATUS
    output: Any = None
    error: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0


@dataclass
class Task:
    id: int
    name: str
    description: str
    retry_count: int
    feedbacks: list = field(default_factory=lambda: [])
