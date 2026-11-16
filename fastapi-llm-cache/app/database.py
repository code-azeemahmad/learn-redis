from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Enforce required environment variables before initializing engine
settings.validate()

engine = create_async_engine(
    settings.POSTGRES_URL,
    echo=False,
    pool_size=10,
    max_overflow=5
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
