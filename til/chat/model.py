import json
import os
from typing import List, Dict, Any
import requests
import google.generativeai as genai
from openai import OpenAI
from til.chat.base import Message, ChatResponse, ChatModel
from dotenv import load_dotenv

load_dotenv("../../configs/.env")


class OllamaModel(ChatModel):
    def __init__(self, host: str = None, model_config: Dict[str, Any] = None):
        super().__init__(model_config)
        self.model_name = None
        self.base_url = host if host else "http://0.0.0.0:11434"
        self.initialize_model()

    def initialize_model(self) -> None:
        self.model_name = self.model_config.get("model_name", "mistral-nemo")

        try:
            response = requests.get(url=f"{self.base_url}/api/tags")
            if response.status_code != 200:
                raise ConnectionError(f"Failed to connect to ollama server at {self.base_url}")

            available_model = [model["name"] for model in response.json()["models"]]

            if self.model_name not in available_model:
                raise ValueError(f"Model {self.model_name} not found, Available Models {available_model}")

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Could not connect to ollama server at {self.base_url}")

    def check_system_prompt(self, system_prompt: str):
        if system_prompt:
            self.add_message(Message(role="system", content=str(system_prompt)))

    def generate_response(self, messages: List[Message]) -> ChatResponse:
        try:
            formatted_messages = [
                {
                    "role": msg.role,
                    "content": msg.content
                } for msg in messages
            ]

            payload = {
                "model": self.model_name,
                "messages": formatted_messages,
                **self.model_config.get("generation_config", {})
            }

            response = requests.post(url=f"{self.base_url}/api/chat", json=payload,
                                     headers={"Content-Type": "application/json"})

            response_data = response.json()

            usage = {
                "prompt_tokens": response_data.get("prompt_eval_count", 0),
                "completion_tokens": response_data.get("eval_count", 0),
                "total_tokens": response_data.get("total_eval_count", 0)
            }

            return ChatResponse(content=response_data["message"]["content"],
                                raw_response=response_data,
                                usage=usage)

        except Exception as e:
            raise Exception(f"Exception in generating response: {e}")


class GeminiModel(ChatModel):
    def __init__(self, model_config: Dict[str, Any]):
        super().__init__(model_config)
        self.gemini_chat = None
        self.model = None
        self.safety_settings = None
        self.generation_config = None
        self.model_name = None
        self.initialize_model()

    def initialize_model(self) -> None:
        if not os.environ["GOOGLE_API_KEY"]:
            raise ValueError("Api key is required for intializing gemini.")

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

        self.model_name = self.model_config.get("model_name", "")
        self.generation_config = self.model_config.get("generation_config", {})
        self.safety_settings = self.model_config.get("safety_settings", [])

        self.model = genai.GenerativeModel(model_name=self.model_name,
                                           safety_settings=self.safety_settings,
                                           generation_config=self.generation_config)
        self.gemini_chat = self.model.start_chat(history=None)

    def check_system_prompt(self, system_prompt: str):
        if system_prompt:
            self.add_message(Message(role="system", content=str(system_prompt)))

            response = self.gemini_chat.send_message(f"This is your prompt: {str(system_prompt)}")

            self.add_message(Message(role="assistant", content=response.text))

    def generate_response(self, messages: List[Message]) -> ChatResponse:
        try:
            last_message = messages[-1]

            response = self.gemini_chat.send_message(last_message.content)

            return ChatResponse(content=response.text, raw_response=response, usage=None)

        except Exception as e:
            raise Exception(f"Error generating response from Gemini")


class OpenaiModel(ChatModel):
    def __init__(self, model_config: Dict[str, Any]):
        super().__init__(model_config=model_config)
        self.model_name = self.model_config.get("model_name", "gpt-4-32k")
        self.openai_model = None

    def initialize_model(self) -> None:
        if not os.environ["OPENAI_API_KEY"]:
            raise f"Api key or organization id is missing"

        self.openai_model = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def check_system_prompt(self, system_prompt: str):
        if system_prompt:
            self.add_message(Message(role="system", content=str(system_prompt)))

    def generate_response(self, messages: List[Message]) -> ChatResponse:
        formatted_messages = [
            {
                "role": msg.role,
                "content": msg.content
            } for msg in messages
        ]

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": False,
            **self.model_config.get("generation_config", {})
        }

        response = self.openai_model.completions.create(payload)

        response_data = response.choices[0].message

        tokens = {
            "prompt_tokens": response_data.usage.prompt_tokens,
            "completion_tokens": response_data.usage.completion_tokens,
            "total_tokens": response_data.usage.total_tokens
        }

        return ChatResponse(content=response_data.content,
                            raw_response=response_data,
                            usage=tokens)


class OpenRouter(ChatModel):
    def __init__(self, model_config: Dict[str, Any]):
        super().__init__(model_config)
        self.model_name = self.model_config.get("model_name")
        self.model_parameters = self.model_config.get("generation_config", {})

    def initialize_model(self) -> None:
        api_key = os.environ["OPENROUTER_API_KEY"]
        if not api_key:
            raise f"`OPEN_ROUTER_API` key is missing"

    def check_system_prompt(self, system_prompt: str):
        if system_prompt:
            self.add_message(Message(role="system", content=str(system_prompt)))

    def generate_response(self, messages: List[Message]) -> ChatResponse:
        formatted_messages = [
            {
                "role": msg.role,
                "content": msg.content
            } for msg in messages
        ]

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"
            },
            data=json.dumps({
                "model": f"{self.model_name}",
                "messages": formatted_messages,
                **self.model_parameters,
            })
        )

        response_data = response.json()

        usage = {
            "prompt_tokens": response_data.get("prompt_eval_count", 0),
            "completion_tokens": response_data.get("eval_count", 0),
            "total_tokens": response_data.get("total_eval_count", 0)
        }

        print(response_data)

        response_data = response_data["choices"][0]["message"]["content"]

        return ChatResponse(content=response_data,
                            raw_response=response_data,
                            usage=usage)


if __name__ == "__main__":
    config = {
        "model_name": "gryphe/mythomax-l2-13b",
        "generation_config": {
            "temperature": 0.0,
            "top_p": 0.8,
            "top_k": 40,
            "response_format": {"type": "json_object"}
        }
    }

    gemini_model = OpenRouter(model_config=config)

    questions = [
        "What is 1+1?",
        "What is the answer to my previous question?",
    ]

    for question in questions:
        response = gemini_model.chat(question)

    for msg in gemini_model.conversation_history:
        print(msg)
