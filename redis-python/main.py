
import asyncio
import os

import redis.asyncio as redis
from redis.exceptions import RedisError

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)

client = redis.from_url(
    REDIS_URL,
    decode_responses=True
)

async def main():
    # Create an asynchronous Redis client
    client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        max_connections=20,
    )

    try:
        # 1. Test Redis connection
        response = await client.ping()
        print("Redis connection:", response)

        # 2. Store a value
        await client.set(
            "user:101",
            "Azeem",
            ex=300
        )

        # 3. Retrieve the value
        user = await client.get("user:101")
        print("User:", user)

        # 4. Check remaining TTL
        ttl = await client.ttl("user:101")
        print("Remaining TTL:", ttl)

        # 5. Check whether the key exists
        exists = await client.exists("user:101")
        print("Key exists:", bool(exists))

        # 6. Delete the key
        deleted = await client.delete("user:101")
        print("Deleted:", bool(deleted))

    finally:
        # Close the Redis client and its connection pool
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
