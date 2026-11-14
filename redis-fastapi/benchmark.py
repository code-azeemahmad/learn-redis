import asyncio
import time
import httpx


async def main():
    url = "http://127.0.0.1:8000/products/101"
    async with httpx.AsyncClient() as client:
        for i in range(5):
            start = time.perf_counter()
            response = await client.get(url)
            elapsed = time.perf_counter() - start
            print(
                f"Request {i + 1}: "
                f"{response.status_code} - "
                f"{elapsed * 1000:.2f} ms"
            )


if __name__ == "__main__":
    asyncio.run(main())
