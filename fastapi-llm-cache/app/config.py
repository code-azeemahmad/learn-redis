import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

# Locate and load .env file from the project root (fastapi-llm-cache/.env)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    """
    Centralized configuration management.
    Strictly reads all parameters from environment variables.
    Does NOT hardcode credentials or secrets into source code.
    """
    # 1. PostgreSQL (Source of Truth)
    # Required: Must be provided via environment variable; no hardcoded credentials fallback
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "")

    # 2. Redis (L1 Exact Cache & Fast Disposable Layer)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # 3. Qdrant (L2 Vector Index & Semantic Cache)
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY") or None

    # 4. Ollama LLM & Embeddings Server
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")

    # 5. Cache & Vector Parameters
    LLM_CACHE_TTL: int = int(os.getenv("LLM_CACHE_TTL", "3600"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "llm_semantic_cache")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))

    def validate(self) -> None:
        """Validates that mandatory environment variables are present."""
        if not self.POSTGRES_URL:
            raise ValueError(
                "POSTGRES_URL environment variable is not set. "
                "Please configure it in .env (e.g., postgresql+asyncpg://<user>:<password>@<host>:<port>/<dbname>)"
            )


def mask_connection_url(url: str) -> str:
    """
    Sanitizes connection URLs (PostgreSQL, Redis, etc.) by redacting embedded passwords.
    Ensures credentials are never exposed in public endpoints, logs, or error responses.
    """
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
        if parsed.password:
            user_part = f"{parsed.username}:***" if parsed.username else ":***"
            netloc = f"{user_part}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
        return url
    except Exception:
        return "<sanitized>"


settings = Settings()
