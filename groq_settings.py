import os

from dotenv import load_dotenv

load_dotenv()

# Groq retired llama-3.3-70b-versatile on 2026-08-16.
# See: https://console.groq.com/docs/deprecations
DEFAULT_GROQ_MODEL = "qwen/qwen3.6-27b"

GROQ_MODEL = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
