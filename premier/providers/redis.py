import json
from typing import Any

try:
    from redis.asyncio.client import Redis as AIORedis

    class AsyncRedisCache:
        def __init__(self, redis: AIORedis, decoder=json.loads, encoder=json.dumps):
            self._redis = redis
            self._encoder = encoder
            self._decoder = decoder

        async def get(self, key: str) -> Any:
            value = await self._redis.get(key)
            if value is None:
                return None
            try:
                return self._decoder(value)
            except (json.JSONDecodeError, TypeError):
                return value

        async def set(self, key: str, value: Any, ex: int | None = None) -> None:
            if isinstance(value, (str, bytes, int, float)):
                await self._redis.set(key, value, ex=ex)
            else:
                await self._redis.set(key, self._encoder(value), ex=ex)

        async def delete(self, key: str) -> None:
            await self._redis.delete(key)

        async def clear(self, keyspace: str = "") -> None:
            if keyspace:
                pattern = f"{keyspace}*"
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
            else:
                await self._redis.flushdb()

        async def exists(self, key: str) -> bool:
            return bool(await self._redis.exists(key))

        async def close(self) -> None:
            await self._redis.aclose()

except ImportError:
    pass
