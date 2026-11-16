from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class LLMQuery(Base):
    """
    PostgreSQL Model: Authoritative, durable source of truth for all LLM queries & responses.
    Vector indexes (Qdrant) and cache layers (Redis) are derived from this table.
    """
    __tablename__ = "llm_queries"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    system_prompt = Column(Text, nullable=True)
    temperature = Column(Float, nullable=False, default=0.2)
    prompt_hash = Column(String(128), nullable=False, index=True)
    qdrant_point_id = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    hit_count = Column(Integer, default=1, nullable=False)
