from pathlib import Path

from .bm25_store import BM25Store
from .chunker import load_policy_chunks
from .config import POLICIES_DIR, TOP_K, HYBRID_CANDIDATES
from .vector_store import VectorStore


class KnowledgeBase:
    def __init__(self):
        self.vector = VectorStore()
        self.bm25 = BM25Store()
        self._load_corpus()

    def _load_corpus(self):
        chunks = []
        for path in sorted(Path(POLICIES_DIR).glob("*.txt")):
            chunks.extend(load_policy_chunks(path))
        for path in sorted(Path(POLICIES_DIR).glob("*.md")):
            chunks.extend(load_policy_chunks(path))

        self.vector.upsert(chunks)
        self.bm25.build([
            {
                "id": c.chunk_id,
                "text": c.text,
                "metadata": c.metadata,
            }
            for c in chunks
        ])

    def rebuild(self):
        self.vector.reset()
        self._load_corpus()

    def naive_search(self, query, top_k=TOP_K, where=None):
        return self.vector.query(query, top_k=top_k, where=where)

    def hybrid_search(self, query, top_k=TOP_K, where=None):
        vector_rows = self.vector.query(
            query,
            top_k=max(HYBRID_CANDIDATES, top_k),
            where=where,
        )
        keyword_rows = self.bm25.search(
            query,
            top_k=max(HYBRID_CANDIDATES, top_k),
            where=where,
        )

        merged = {}
        for rank, row in enumerate(vector_rows):
            merged.setdefault(row["id"], {"row": row, "v_rank": rank + 1, "b_rank": None})
        for rank, row in enumerate(keyword_rows):
            entry = merged.setdefault(
                row["id"],
                {"row": row, "v_rank": None, "b_rank": rank + 1},
            )
            entry["b_rank"] = rank + 1
            entry["row"]["bm25_score"] = row["bm25_score"]

        # Reciprocal Rank Fusion avoids comparing BM25 and cosine scales directly.
        scored = []
        for entry in merged.values():
            rrf = 0.0
            if entry["v_rank"] is not None:
                rrf += 1.0 / (60 + entry["v_rank"])
            if entry["b_rank"] is not None:
                rrf += 1.0 / (60 + entry["b_rank"])
            row = dict(entry["row"])
            row["hybrid_score"] = rrf
            scored.append(row)

        scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return scored[:top_k]


_kb = None


def get_knowledge_base():
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def search_knowledge_base(query, top_k=TOP_K, mode="hybrid", where=None):
    kb = get_knowledge_base()
    if mode == "naive":
        return kb.naive_search(query, top_k, where)
    return kb.hybrid_search(query, top_k, where)
