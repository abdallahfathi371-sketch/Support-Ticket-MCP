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

    def __init__(self, client: object | None = None, use_real_llm: bool | None = None, **kwargs):
        """
        If `client` is provided, it is used directly (test injection). Otherwise
        `use_real_llm` controls whether to instantiate a real Groq client. When
        neither is provided, the environment variable PLANNING_USE_REAL_LLM
        determines behavior. In non-real mode the model behaves deterministically
        to make unit tests reproducible.
        """
        super().__init__(**kwargs)

        if use_real_llm is None:
            env_val = os.getenv("PLANNING_USE_REAL_LLM", "false").lower()
            use_real_llm = env_val in ("1", "true", "yes")

        if client is not None:
            object.__setattr__(self, "_client", client)
            object.__setattr__(self, "_use_real_llm", True)
            return

        if use_real_llm:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "PLANNING_USE_REAL_LLM requested but GROQ_API_KEY is not set."
                )
            object.__setattr__(
                self,
                "_client",
                Groq(api_key=api_key),
            )
            object.__setattr__(self, "_use_real_llm", True)
        else:
            # Deterministic, test-friendly mode
            object.__setattr__(self, "_client", None)
            object.__setattr__(self, "_use_real_llm", False)

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

        # If operating without a real Groq client, return a deterministic
        # synthetic response to keep unit tests stable.
        if not getattr(self, "_use_real_llm", False) or self._client is None:
            # Find last human/user message content to base the fake reply on
            last_content = ""
            for m in reversed(messages):
                if isinstance(m, tuple):
                    role, content = m
                    if role in ("human", "user"):
                        last_content = str(content)
                        break
                elif isinstance(m, BaseMessage) and getattr(m, "type", None) in ("human", "user"):
                    last_content = m.content
                    break

            reply = f"FAKE_RESPONSE: {str(last_content)[:400]}" or "FAKE_RESPONSE"

            message = AIMessage(content=reply)
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])

        import time
        from .metrics import record_llm_call

        t0 = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=self._messages_to_groq(messages),
            temperature=self.temperature,
        )
        t1 = time.perf_counter()

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "Groq returned an empty response."
            )

        # Approximate token count as chars / 4
        approx_tokens = max(1, int((len(str(messages)) + len(str(content))) / 4))
        record_llm_call(latency=t1 - t0, approx_tokens=approx_tokens)

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

            # If not using a real LLM, provide deterministic, minimal valid
            # structured outputs so unit tests can run offline.
            if not getattr(self, "_use_real_llm", False) or self._client is None:
                # Heuristics for common schemas used in this repo
                name = schema.__name__

                if name == "ThoughtCandidates":
                    # Return two simple candidates
                    return schema.model_validate({
                        "candidates": ["Candidate A", "Candidate B"]
                    })

                if name == "ThoughtEvaluation":
                    return schema.model_validate({
                        "score": 0.5,
                        "rationale": "Heuristic evaluation",
                    })

                # Special-case LATSActionBatch: produce n_actions proposals
                if name == "LATSActionBatch":
                    # Try to extract requested number of actions from the prompt
                    last = groq_messages[-1]["content"] if groq_messages else ""
                    import re

                    m = re.search(r"Propose exactly (\d+)", last)
                    try:
                        n = int(m.group(1)) if m else 2
                    except Exception:
                        n = 2

                    actions = []
                    for i in range(1, n + 1):
                        actions.append({
                            "action": f"Action {i}",
                            "state": f"Proposed solution {i}: perform step {i} to address the task."
                        })

                    return schema.model_validate({"actions": actions})

                # Generic fallback: try to construct minimal valid instance
                sample = {}
                for fname in getattr(schema, "model_fields", {}).keys():
                    # Heuristic defaults based on common field names
                    lower = fname.lower()
                    if "score" in lower or "prob" in lower:
                        sample[fname] = 0.5
                    elif "candidates" in lower or lower.endswith("s") or "list" in lower:
                        sample[fname] = []
                    elif "count" in lower or "id" in lower:
                        sample[fname] = 0
                    elif "success" in lower or "flag" in lower or "is_" in lower:
                        sample[fname] = False
                    else:
                        sample[fname] = ""

                return schema.model_validate(sample)

            import time
            from .metrics import record_llm_call

            t0 = time.perf_counter()
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=groq_messages,
                temperature=self.temperature,
                response_format={
                    "type": "json_object"
                },
            )
            t1 = time.perf_counter()

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError(
                    "Groq returned an empty structured response."
                )

            # Approximate token count as chars / 4
            approx_tokens = max(1, int((len(str(groq_messages)) + len(str(content))) / 4))
            record_llm_call(latency=t1 - t0, approx_tokens=approx_tokens)

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