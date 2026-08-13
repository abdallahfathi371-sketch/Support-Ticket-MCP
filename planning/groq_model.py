import json
import os
from typing import Any, Type

from dotenv import load_dotenv
from groq import Groq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, ConfigDict


load_dotenv()


class GroqChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str = "llama-3.3-70b-versatile"
    temperature: float = 0.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set in the environment."
            )

        object.__setattr__(
            self,
            "_client",
            Groq(api_key=api_key),
        )

    @property
    def _llm_type(self) -> str:
        return "groq"

    def _messages_to_groq(
        self,
        messages,
    ) -> list[dict[str, str]]:
        groq_messages = []

        for message in messages:

            if isinstance(message, tuple):
                role, content = message

                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"

            elif isinstance(message, BaseMessage):

                if message.type == "system":
                    role = "system"
                elif message.type == "human":
                    role = "user"
                elif message.type == "ai":
                    role = "assistant"
                else:
                    role = "user"

                content = message.content

            else:
                raise TypeError(
                    f"Unsupported message type: {type(message)}"
                )

            groq_messages.append(
                {
                    "role": role,
                    "content": str(content),
                }
            )

        return groq_messages

    def _generate(
        self,
        messages: list[BaseMessage],
        stop=None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:

        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=self._messages_to_groq(messages),
            temperature=self.temperature,
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "Groq returned an empty response."
            )

        message = AIMessage(content=content)

        generation = ChatGeneration(
            message=message
        )

        return ChatResult(
            generations=[generation]
        )

    def with_structured_output(
        self,
        schema: Type[BaseModel],
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ):
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise TypeError(
                "GroqChatModel currently requires a Pydantic BaseModel schema."
            )

        json_schema = schema.model_json_schema()

        def invoke_structured(messages):
            structured_instruction = (
                "\n\nIMPORTANT: Return ONLY valid JSON.\n"
                "The JSON must follow this schema exactly:\n"
                f"{json.dumps(json_schema, indent=2)}"
            )

            groq_messages = self._messages_to_groq(messages)

            if groq_messages:
                groq_messages[-1]["content"] += structured_instruction

            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=groq_messages,
                temperature=self.temperature,
                response_format={
                    "type": "json_object"
                },
            )

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError(
                    "Groq returned an empty structured response."
                )

            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Groq returned invalid JSON: {content}"
                ) from exc

            try:
                return schema.model_validate(data)
            except Exception as exc:
                raise RuntimeError(
                    f"Groq response did not match "
                    f"{schema.__name__}: {data}"
                ) from exc

        return RunnableLambda(invoke_structured)