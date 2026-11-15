
import asyncio
import redis.asyncio as redis


async def main():
    client = redis.Redis(
        host="127.0.0.1",
        port=6379,
        socket_connect_timeout=5,
        socket_timeout=5,
        decode_responses=True,
    )

    try:
        for i in range(10):
            print(i + 1, await client.ping())
            await asyncio.sleep(2)
    except Exception as error:
        print(type(error).__name__, str(error))
    finally:
        await client.aclose()


asyncio.run(main())
