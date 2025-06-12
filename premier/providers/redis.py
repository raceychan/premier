import json
from typing import Any, Generic, TypeVar

try:
    from redis.asyncio.client import Redis as AIORedis

    T = TypeVar("T")

    class AsyncRedisCacheAdapter:
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

    class AsyncRedisQueueAdapter(Generic[T]):
        def __init__(
            self,
            redis: AIORedis,
            name: str,
            maxsize: int,
            encoder=json.dumps,
            decoder=json.loads,
        ):
            self._redis = redis
            self._name = name
            self._maxsize = maxsize
            self._encoder = encoder
            self._decoder = decoder

        async def put(self, item: T) -> None:
            current_size = await self._redis.llen(self._name)
            if current_size >= self._maxsize:
                from premier.throttler.errors import QueueFullError

                raise QueueFullError("Queue is full. Cannot add more items.")

            serialized = self._encoder(item)
            await self._redis.lpush(self._name, serialized)

        async def get(self, block: bool = True, *, timeout: float = 0) -> T | None:
            if block:
                result = await self._redis.brpop([self._name], timeout=timeout)
                if result is None:
                    return None
                _, item_bytes = result
            else:
                item_bytes = await self._redis.rpop(self._name)
                if item_bytes is None:
                    return None

            return self._decoder(item_bytes)

        async def qsize(self) -> int:
            return await self._redis.llen(self._name)

        async def empty(self) -> bool:
            return await self.qsize() == 0

        async def full(self) -> bool:
            return await self.qsize() >= self._maxsize

        @property
        def capacity(self) -> int:
            return self._maxsize

        async def clear(self) -> None:
            await self._redis.delete(self._name)

        async def close(self) -> None:
            await self._redis.aclose()

except ImportError:
    pass
