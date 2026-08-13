from pydantic import BaseModel, Field

from planning.groq_model import GroqChatModel


class TestOutput(BaseModel):
    answer: str = Field(min_length=1)


llm = GroqChatModel()

result = llm.with_structured_output(TestOutput).invoke(
    [
        (
            "human",
            "Return the word Hello as the answer."
        )
    ]
)
print(result)