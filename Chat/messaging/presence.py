"""Redis-backed, multi-tab user presence for ChitChat WebSockets."""
from __future__ import annotations

import time

from django.conf import settings
from redis.asyncio import Redis

PRESENCE_TTL_SECONDS = 60
PRESENCE_SET_TTL_SECONDS = 90
_redis_client: Redis | None = None


def redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        # Override CHAT_REDIS_URL in settings/environment for another Redis host.
        url = getattr(settings, "CHAT_REDIS_URL", "redis://127.0.0.1:6379/1")
        _redis_client = Redis.from_url(url, decode_responses=True)
    return _redis_client


def _user_key(user_id: int) -> str:
    return f"chitchat:presence:user:{user_id}"


def _connection_key(user_id: int, connection_id: str) -> str:
    return f"chitchat:presence:connection:{user_id}:{connection_id}"


async def touch_connection(user_id: int, connection_id: str) -> None:
    """Register/refresh one tab/device without affecting other connections."""
    now = time.time()
    client = redis_client()
    pipe = client.pipeline(transaction=True)
    pipe.zadd(_user_key(user_id), {connection_id: now})
    pipe.expire(_user_key(user_id), PRESENCE_SET_TTL_SECONDS)
    pipe.set(
        _connection_key(user_id, connection_id),
        "1",
        ex=PRESENCE_TTL_SECONDS,
    )
    await pipe.execute()


async def remove_connection(user_id: int, connection_id: str) -> None:
    client = redis_client()
    pipe = client.pipeline(transaction=True)
    pipe.delete(_connection_key(user_id, connection_id))
    pipe.zrem(_user_key(user_id), connection_id)
    await pipe.execute()


async def is_user_online(user_id: int) -> bool:
    """True if at least one tab/device refreshed presence within the TTL."""
    now = time.time()
    client = redis_client()
    key = _user_key(user_id)
    pipe = client.pipeline(transaction=True)
    pipe.zremrangebyscore(key, "-inf", now - PRESENCE_TTL_SECONDS)
    pipe.zcard(key)
    pipe.expire(key, PRESENCE_SET_TTL_SECONDS)
    result = await pipe.execute()
    return int(result[1]) > 0
