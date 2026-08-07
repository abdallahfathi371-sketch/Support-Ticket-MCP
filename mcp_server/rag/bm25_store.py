import re
from rank_bm25 import BM25Plus


def tokenize(text):
    return re.findall(r"[a-zA-Z0-9_./-]+", text.lower())


class BM25Store:
    def __init__(self):
        self.rows = []
        self.index = None

    def build(self, rows):
        self.rows = list(rows)
        corpus = [tokenize(row["text"]) for row in self.rows]
        self.index = BM25Plus(corpus) if corpus else None

    def search(self, query, top_k=10, where=None):
        if not self.index:
            return []

        tokens = tokenize(query)
        scores = self.index.get_scores(tokens)
        candidates = []

        for i, score in enumerate(scores):
            row = self.rows[i]
            if where and any(row["metadata"].get(k) != v for k, v in where.items()):
                continue
            candidates.append((float(score), row))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [
            {**row, "bm25_score": score}
            for score, row in candidates[:top_k]
        ]
