from pathlib import Path

from .keyword_store import KeywordStore
from .chunker import load_policy_chunks


knowledge_store = KeywordStore()


POLICIES_DIR = Path(__file__).parent.parent / "policies"


def build_knowledge_base():

    for file in POLICIES_DIR.glob("*.md"):

        chunks = load_policy_chunks(file)

        for chunk in chunks:

            knowledge_store.upsert(
                payload=chunk,
                metadata={
                    "document": file.stem
                }
            )


def search_knowledge_base(query: str, top_k: int = 3):

    return knowledge_store.query(
        query_text=query,
        top_k=top_k
    )


build_knowledge_base()