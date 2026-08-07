import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
POLICIES_DIR = ROOT / "mcp_server" / "policies"
CHROMA_DIR = ROOT / "db" / "chroma_rag"
COLLECTION_NAME = os.getenv("RAG_COLLECTION", "coderift_policies")

EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "700"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("RAG_TOP_K", "5"))
HYBRID_CANDIDATES = int(os.getenv("RAG_HYBRID_CANDIDATES", "10"))
SELF_RAG_MIN_RELEVANCE = float(os.getenv("SELF_RAG_MIN_RELEVANCE", "0.55"))
SELF_RAG_MIN_SUPPORT = float(os.getenv("SELF_RAG_MIN_SUPPORT", "0.65"))
MAX_AGENTIC_ROUNDS = int(os.getenv("RAG_MAX_AGENTIC_ROUNDS", "2"))
