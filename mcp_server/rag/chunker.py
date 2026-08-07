from dataclasses import dataclass
from pathlib import Path
import re

from .config import CHUNK_SIZE, CHUNK_OVERLAP


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict


def _split_words(text: str):
    return re.findall(r"\S+", text)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    words = _split_words(text)
    if not words:
        return []

    chunks = []
    start = 0
    index = 0

    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(start + 1, end - overlap)
        index += 1

    return chunks


def load_policy_chunks(policy_path: Path):
    text = policy_path.read_text(encoding="utf-8")
    raw = chunk_text(text)

    return [
        Chunk(
            chunk_id=f"{policy_path.stem}:{i}",
            text=chunk,
            metadata={
                "document": policy_path.stem,
                "source": str(policy_path),
                "chunk_index": i,
            },
        )
        for i, chunk in enumerate(raw)
    ]
