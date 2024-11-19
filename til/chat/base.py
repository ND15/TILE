from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Any, Optional, Dict


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ChatResponse:
    """Represents a response from the chat model."""
    content: str
    raw_response: Any
    usage: Optional[Dict[str, int]] = None


class ChatModel(ABC):
    """Abstract base class for chat-based language models."""

    def __init__(self, model_config: Dict[str, Any]):
        self.system_prompt = None
        self.model_config = model_config
        self.conversation_history: List[Message] = []

    @abstractmethod
    def initialize_model(self) -> None:
        pass

    @abstractmethod
    def generate_response(self, messages: List[Message]) -> ChatResponse:
        pass

    def check_system_prompt(self, system_prompt: str):
        pass

    def add_message(self, message: Message) -> None:
        self.conversation_history.append(message)

    def chat(self, user_input: str) -> ChatResponse:
        self.add_message(Message(role="user", content=user_input))

        response = self.generate_response(self.conversation_history)

        self.add_message(Message(role="assistant", content=response.content))

        return response

    def clear_history(self) -> None:
        self.conversation_history = []
