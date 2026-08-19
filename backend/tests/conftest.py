import os
import sys
from pathlib import Path

# Ensure `app` package is importable when running `pytest` from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg2://raguser:ragpassword@localhost:5432/ragdb")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("LLM_PROVIDER", "ollama")
