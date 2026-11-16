import logging
from typing import Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        ollama_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.EMBEDDING_MODEL
    ):
        self.ollama_url = ollama_url
        self.model = model

    async def get_embedding(self, text: str) -> list[float]:
        """
        Generates a 768-dimensional dense vector embedding using Ollama nomic-embed-text.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text.strip()
                    }
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                if not embedding or not isinstance(embedding, list):
                    raise ValueError(f"Invalid embedding received from Ollama: {data}")
                return embedding
            except httpx.HTTPError as err:
                logger.error("Failed to generate embedding from Ollama: %s", err)
                raise err
