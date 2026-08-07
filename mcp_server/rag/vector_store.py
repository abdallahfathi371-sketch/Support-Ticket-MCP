from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

from .config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL


class VectorStore:
    """
    Chroma uses an HNSW ANN index locally. Metadata is stored with each
    vector and can be filtered during the collection query.
    """

    def __init__(self):
        Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)

    def reset(self):
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks):
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        embeddings = self.encoder.encode(
            documents,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def query(self, text, top_k=5, where=None):
        embedding = self.encoder.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0].tolist()

        kwargs = {
            "query_embeddings": [embedding],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where

        result = self.collection.query(**kwargs)
        rows = []

        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for i, chunk_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 1.0
            rows.append({
                "id": chunk_id,
                "text": docs[i],
                "metadata": metas[i] or {},
                "vector_distance": float(distance),
                "vector_score": max(0.0, min(1.0, 1.0 - float(distance))),
            })

        return rows
