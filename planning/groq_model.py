from __future__ import annotations

import json
import os
import time
from typing import Any, Type

from dotenv import load_dotenv
from groq import Groq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, ConfigDict

from groq_settings import GROQ_MODEL

load_dotenv()


class GroqChatModel(BaseChatModel):
    """
    LangChain-compatible Groq chat model used by the planning
    and state-graph reasoning layers.

    Supports:
    - normal chat generation
    - structured Pydantic output
    - deterministic offline/test mode
    - real Groq API mode
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    model_name: str = GROQ_MODEL
    temperature: float = 0.0

    def __init__(
        self,
        client: object | None = None,
        use_real_llm: bool | None = None,
        **kwargs,
    ):
        """
        Parameters
        ----------
        client:
            Optional injected Groq-like client, mainly useful
            for tests.

        use_real_llm:
            Explicitly control whether the real Groq API is used.

            If None, the environment variable
            PLANNING_USE_REAL_LLM determines the mode.
        """

        super().__init__(**kwargs)

        if use_real_llm is None:
            env_val = os.getenv(
                "PLANNING_USE_REAL_LLM",
                "false",
            ).lower()

            use_real_llm = env_val in {
                "1",
                "true",
                "yes",
                "on",
            }

        if client is not None:

            object.__setattr__(
                self,
                "_client",
                client,
            )

            object.__setattr__(
                self,
                "_use_real_llm",
                True,
            )

            return

        if use_real_llm:

            api_key = os.getenv(
                "GROQ_API_KEY"
            )

            if not api_key:
                raise RuntimeError(
                    "Real Groq mode requested, "
                    "but GROQ_API_KEY is not set."
                )

            object.__setattr__(
                self,
                "_client",
                Groq(
                    api_key=api_key
                ),
            )

            object.__setattr__(
                self,
                "_use_real_llm",
                True,
            )

        else:

            # Deterministic mode for tests and development.
            object.__setattr__(
                self,
                "_client",
                None,
            )

            object.__setattr__(
                self,
                "_use_real_llm",
                False,
            )

    @property
    def _llm_type(self) -> str:
        return "groq"

    # =========================================================
    # Message conversion
    # =========================================================

    def _messages_to_groq(
        self,
        messages,
    ) -> list[dict[str, str]]:

        groq_messages: list[
            dict[str, str]
        ] = []

        for message in messages:

            if isinstance(message, tuple):

                role, content = message

                if role == "human":
                    role = "user"

                elif role == "ai":
                    role = "assistant"

            elif isinstance(
                message,
                BaseMessage,
            ):

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
                    f"Unsupported message type: "
                    f"{type(message)}"
                )

            groq_messages.append(
                {
                    "role": str(role),
                    "content": str(content),
                }
            )

        return groq_messages

    # =========================================================
    # Normal generation
    # =========================================================

    def _generate(
        self,
        messages: list[BaseMessage],
        stop=None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:

        # -----------------------------------------------------
        # Deterministic test mode
        # -----------------------------------------------------

        if (
            not getattr(
                self,
                "_use_real_llm",
                False,
            )
            or self._client is None
        ):

            last_content = ""

            for message in reversed(
                messages
            ):

                if isinstance(
                    message,
                    tuple,
                ):

                    role, content = message

                    if role in {
                        "human",
                        "user",
                    }:

                        last_content = str(
                            content
                        )

                        break

                elif (
                    isinstance(
                        message,
                        BaseMessage,
                    )
                    and getattr(
                        message,
                        "type",
                        None,
                    )
                    in {
                        "human",
                        "user",
                    }
                ):

                    last_content = str(
                        message.content
                    )

                    break

            reply = (
                f"FAKE_RESPONSE: "
                f"{last_content[:400]}"
                if last_content
                else "FAKE_RESPONSE"
            )

            ai_message = AIMessage(
                content=reply
            )

            generation = ChatGeneration(
                message=ai_message
            )

            return ChatResult(
                generations=[
                    generation
                ]
            )

        # -----------------------------------------------------
        # Real Groq mode
        # -----------------------------------------------------

        from .metrics import (
            record_llm_call,
        )

        t0 = time.perf_counter()

        response = (
            self._client.chat.completions.create(
                model=self.model_name,
                messages=self._messages_to_groq(
                    messages
                ),
                temperature=self.temperature,
            )
        )

        t1 = time.perf_counter()

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:
            raise RuntimeError(
                "Groq returned an empty response."
            )

        approx_tokens = max(
            1,
            int(
                (
                    len(str(messages))
                    + len(str(content))
                )
                / 4
            ),
        )

        record_llm_call(
            latency=t1 - t0,
            approx_tokens=approx_tokens,
        )

        ai_message = AIMessage(
            content=content
        )

        generation = ChatGeneration(
            message=ai_message
        )

        return ChatResult(
            generations=[
                generation
            ]
        )

    # =========================================================
    # Structured output
    # =========================================================

    def with_structured_output(
        self,
        schema: Type[BaseModel],
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ):

        if (
            not isinstance(
                schema,
                type,
            )
            or not issubclass(
                schema,
                BaseModel,
            )
        ):
            raise TypeError(
                "GroqChatModel currently requires "
                "a Pydantic BaseModel schema."
            )

        json_schema = (
            schema.model_json_schema()
        )

        def invoke_structured(
            messages,
        ):
            structured_instruction = (
                "\n\nIMPORTANT: Return ONLY valid JSON.\n"
                "The JSON must follow this schema exactly:\n"
                f"{json.dumps(json_schema, indent=2)}"
            )

            groq_messages = (
                self._messages_to_groq(
                    messages
                )
            )

            if groq_messages:

                groq_messages[-1][
                    "content"
                ] += structured_instruction

            # -------------------------------------------------
            # Deterministic structured mode
            # -------------------------------------------------

            if (
                not getattr(
                    self,
                    "_use_real_llm",
                    False,
                )
                or self._client is None
            ):

                name = schema.__name__

                # Tree of Thoughts
                if name == "ThoughtCandidates":

                    return schema.model_validate(
                        {
                            "candidates": [
                                "Candidate A",
                                "Candidate B",
                            ]
                        }
                    )

                # Thought evaluation
                if name == "ThoughtEvaluation":

                    return schema.model_validate(
                        {
                            "score": 0.5,
                            "rationale": (
                                "Heuristic evaluation"
                            ),
                        }
                    )

                # LATS action batch
                if name == "LATSActionBatch":

                    last = (
                        groq_messages[-1]["content"]
                        if groq_messages
                        else ""
                    )

                    import re

                    match = re.search(
                        r"Propose exactly (\d+)",
                        last,
                    )

                    try:
                        number_of_actions = (
                            int(
                                match.group(1)
                            )
                            if match
                            else 2
                        )

                    except Exception:
                        number_of_actions = 2

                    actions = []

                    for i in range(
                        1,
                        number_of_actions + 1,
                    ):

                        actions.append(
                            {
                                "action": (
                                    f"Action {i}"
                                ),
                                "state": (
                                    f"Proposed solution "
                                    f"{i}: perform step "
                                    f"{i} to address "
                                    f"the task."
                                ),
                            }
                        )

                    return schema.model_validate(
                        {
                            "actions": actions
                        }
                    )

                # ---------------------------------------------
                # Generic deterministic fallback
                # ---------------------------------------------

                sample: dict[str, Any] = {}
                prompt = ""
                if groq_messages:
                    prompt = str(groq_messages[-1].get("content", ""))

                for field_name in getattr(
                    schema,
                    "model_fields",
                    {},
                ).keys():

                    lower = (
                        field_name.lower()
                    )

                    if (
                        "score" in lower
                        or "prob" in lower
                    ):

                        sample[field_name] = 0.5

                    elif (
                        "candidates" in lower
                        or lower.endswith("s")
                        or "list" in lower
                    ):

                        sample[field_name] = []

                    elif (
                        "count" in lower
                        or lower.endswith("id")
                        or lower == "id"
                    ):

                        sample[field_name] = 0

                    elif (
                        "success" in lower
                        or "flag" in lower
                        or lower.startswith("is_")
                    ):

                        sample[field_name] = False

                    else:
                        value = "Example"
                        if "hello" in prompt.lower():
                            value = "Hello"
                        elif "answer" in lower or "response" in lower:
                            value = "Completed"
                        elif "summary" in lower:
                            value = "Summary"
                        elif "status" in lower:
                            value = "pending"
                        elif "reason" in lower:
                            value = "Deterministic fallback"

                        sample[field_name] = value

                return schema.model_validate(
                    sample
                )

            # -------------------------------------------------
            # Real Groq structured mode
            # -------------------------------------------------

            from .metrics import (
                record_llm_call,
            )

            t0 = time.perf_counter()

            response = (
                self._client
                .chat
                .completions
                .create(
                    model=self.model_name,
                    messages=groq_messages,
                    temperature=self.temperature,
                    response_format={
                        "type": "json_object"
                    },
                )
            )

            t1 = time.perf_counter()

            content = (
                response
                .choices[0]
                .message
                .content
            )

            if not content:
                raise RuntimeError(
                    "Groq returned an empty "
                    "structured response."
                )

            approx_tokens = max(
                1,
                int(
                    (
                        len(
                            str(
                                groq_messages
                            )
                        )
                        + len(
                            str(content)
                        )
                    )
                    / 4
                ),
            )

            record_llm_call(
                latency=t1 - t0,
                approx_tokens=approx_tokens,
            )

            # -------------------------------------------------
            # Parse JSON
            # -------------------------------------------------

            try:

                data = json.loads(
                    content
                )

            except json.JSONDecodeError as exc:

                raise RuntimeError(
                    "Groq returned invalid JSON: "
                    f"{content}"
                ) from exc

            # -------------------------------------------------
            # Validate Pydantic schema
            # -------------------------------------------------

            try:

                return schema.model_validate(
                    data
                )

            except Exception as exc:

                raise RuntimeError(
                    "Groq response did not match "
                    f"{schema.__name__}: {data}"
                ) from exc

        return RunnableLambda(
            invoke_structured
        )