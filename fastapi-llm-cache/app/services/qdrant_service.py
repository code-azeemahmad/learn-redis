import logging
import uuid
from typing import Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(
        self,
        qdrant_url: str | None = None,
        api_key: str | None = None
    ):
        self.qdrant_url = (qdrant_url or settings.QDRANT_URL).rstrip("/")
        self.api_key = api_key or settings.QDRANT_API_KEY

    def _get_headers(self) -> dict[str, str]:
        headers = {}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    async def ensure_collection(
        self,
        collection_name: str | None = None,
        vector_size: int | None = None
    ) -> None:
        """
        Ensures that the Qdrant vector collection exists with the specified dimension (768)
        and Cosine distance metric. Creates it automatically if missing.
        """
        cname = collection_name or settings.COLLECTION_NAME
        vsize = vector_size or settings.EMBEDDING_DIM

        async with httpx.AsyncClient(timeout=10.0, headers=self._get_headers()) as client:
            res = await client.get(f"{self.qdrant_url}/collections/{cname}")
            if res.status_code == 200:
                logger.info("Qdrant collection '%s' already exists", cname)
                return

            logger.info("Creating Qdrant collection '%s' with dimension %d", cname, vsize)
            create_payload = {
                "vectors": {
                    "size": vsize,
                    "distance": "Cosine"
                }
            }
            create_res = await client.put(
                f"{self.qdrant_url}/collections/{cname}",
                json=create_payload
            )
            create_res.raise_for_status()
            logger.info("Qdrant collection '%s' created successfully", cname)

    async def search_similar(
        self,
        vector: list[float],
        collection_name: str | None = None,
        threshold: float | None = None
    ) -> dict[str, Any] | None:
        """
        Performs semantic vector search in Qdrant using Cosine similarity.
        Returns the top matching point if its similarity score exceeds the threshold.
        """
        cname = collection_name or settings.COLLECTION_NAME
        thresh = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD

        async with httpx.AsyncClient(timeout=10.0, headers=self._get_headers()) as client:
            search_payload = {
                "vector": vector,
                "limit": 1,
                "with_payload": True,
                "score_threshold": thresh
            }
            res = await client.post(
                f"{self.qdrant_url}/collections/{cname}/points/search",
                json=search_payload
            )
            res.raise_for_status()
            data = res.json()
            results = data.get("result", [])
            if results:
                top_match = results[0]
                return {
                    "id": top_match.get("id"),
                    "score": top_match.get("score"),
                    "payload": top_match.get("payload", {})
                }
            return None

    async def upsert_point(
        self,
        vector: list[float],
        payload: dict[str, Any],
        point_id: str | None = None,
        collection_name: str | None = None
    ) -> str:
        """
        Upserts a vector and metadata payload into Qdrant.
        """
        cname = collection_name or settings.COLLECTION_NAME
        pid = point_id or str(uuid.uuid4())
        async with httpx.AsyncClient(timeout=10.0, headers=self._get_headers()) as client:
            upsert_payload = {
                "points": [
                    {
                        "id": pid,
                        "vector": vector,
                        "payload": payload
                    }
                ]
            }
            res = await client.put(
                f"{self.qdrant_url}/collections/{cname}/points?wait=true",
                json=upsert_payload
            )
            res.raise_for_status()
            logger.info("Upserted point %s to Qdrant collection '%s'", pid, cname)
            return pid

    async def count_points(self, collection_name: str | None = None) -> int:
        """
        Returns the total number of indexed vectors in Qdrant collection.
        """
        cname = collection_name or settings.COLLECTION_NAME
        async with httpx.AsyncClient(timeout=10.0, headers=self._get_headers()) as client:
            try:
                res = await client.post(
                    f"{self.qdrant_url}/collections/{cname}/points/count",
                    json={"exact": True}
                )
                if res.status_code == 200:
                    return res.json().get("result", {}).get("count", 0)
                return 0
            except Exception:
                return 0
