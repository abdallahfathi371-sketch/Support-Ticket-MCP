from pathlib import Path


def chunk_text(text: str, chunk_size: int = 300):
    """
    Split text into small chunks.
    """

    chunks = []

    current = ""

    for line in text.splitlines():

        if len(current) + len(line) < chunk_size:
            current += line + "\n"

        else:
            chunks.append(current.strip())
            current = line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


def load_policy_chunks(policy_path: Path):

    with open(policy_path, "r", encoding="utf-8") as f:
        text = f.read()

    return chunk_text(text)