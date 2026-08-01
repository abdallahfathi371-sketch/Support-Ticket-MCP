import re
from rank_bm25 import BM25Plus


def tokenize(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())


class KeywordStore:

    def __init__(self):
        self.rows = []
        self._bm25 = None
        self._dirty = True

    def upsert(self, payload, metadata):
        self.rows.append({
            "payload": payload,
            "metadata": metadata
        })
        self._dirty = True

    def _rebuild_index(self):
        corpus = [
            tokenize(row["payload"])
            for row in self.rows
        ]

        if corpus:
            self._bm25 = BM25Plus(corpus)
        else:
            self._bm25 = None

        self._dirty = False

    def query(self, query_text, top_k=3, filter=None):

        if self._dirty:
            self._rebuild_index()

        if self._bm25 is None:
            return []

        query_tokens = tokenize(query_text)

        scores = self._bm25.get_scores(query_tokens)

        results = []

        for i, row in enumerate(self.rows):

            if filter:

                ok = True

                for key, value in filter.items():

                    if row["metadata"].get(key) != value:
                        ok = False
                        break

                if not ok:
                    continue

            overlap = set(query_tokens) & set(tokenize(row["payload"]))

            if overlap:
                results.append((scores[i], row))

        results.sort(key=lambda x: x[0], reverse=True)

        return [
            row
            for score, row in results[:top_k]
        ]