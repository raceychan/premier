import json
import typing as ty

from redis.asyncio.client import Redis as AIORedis
from redis.client import Redis  # type: ignore

from premier.errors import BucketFullError

__REF = """
[redis-queue](https://redis.io/glossary/redis-queue/)
-----
Sometimes, you may want to add a task to the queue but delay its execution until a later time. While Redis does not directly support delayed tasks, you can implement them using sorted sets in combination with regular queues.

Here’s how you can schedule a task to be added to the queue after a delay:

Add the task to a sorted set with a score that represents the time when the task should be executed:
ZADD delayedqueue 1633024800 "Task1"
Have a consumer that periodically checks the sorted set and moves tasks that are due to the main queue:
ZRANGEBYSCORE delayedqueue 0 <current_time>
RPOPLPUSH tempqueue myqueue
"""


class RedisQueue:
    def __init__(self, client: Redis, *, name: str, queue_size: int):
        self._client = client
        self._name = name
        self._size = queue_size

    def qsize(self) -> int:
        """Return the approximate size of the queue."""
        size = self._client.llen(self._name)
        return size  # type: ignore

    def empty(self) -> bool:
        """Return True if the queue is empty, False otherwise."""
        return self.qsize() == 0

    def put(
        self, item: ty.Any, block: bool = True, timeout: float | None = None
    ) -> None:
        """Put an item into the queue."""
        if self.full():
            raise BucketFullError("Bucket is full. Cannot add more items.")
        serialized_item = json.dumps(item)
        self._client.lpush(self._name, serialized_item)

    def full(self) -> bool:
        return self.qsize() >= self._size

    def get(self, block: bool = True, timeout: float | None = None) -> ty.Any:
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available.
        """
        if block:
            if timeout is None:
                # Blocking get with no timeout
                item = self._client.brpop(self._name)
            else:
                # Blocking get with a timeout
                item = self._client.brpop(self._name, timeout=timeout)
        else:
            item = self._client.rpop(self._name)

        if item:
            # brpop returns a tuple (key, value), rpop returns just the value
            item_value = item[1] if isinstance(item, tuple) else item
            return json.loads(item_value)
        else:
            raise queue.Empty("No items in queue")

    def clear(self) -> None:
        """Clear all items from the queue."""
        self._client.delete(self._name)

    def close(self) -> None:
        """Close the Redis connection."""
        self._client.close()

    def __del__(self):
        self.close()


class AsyncRedisQueue:
    def __init__(self, client: AIORedis, *, name: str, queue_size: int):
        self._client = client
        self._name = name
        self._size = queue_size

    async def qsize(self) -> int:
        """Return the approximate size of the queue."""
        size = await self._client.llen(self._name)
        return size  # type: ignore

    async def empty(self) -> bool:
        """Return True if the queue is empty, False otherwise."""
        return await self.qsize() == 0

    async def put(
        self, item: ty.Any, block: bool = True, timeout: float | None = None
    ) -> None:
        """Put an item into the queue."""
        if await self.full():
            raise BucketFullError("Bucket is full. Cannot add more items.")
        serialized_item = json.dumps(item)
        await self._client.lpush(self._name, serialized_item)

    async def full(self) -> bool:
        return await self.qsize() >= self._size

    async def get(self, block: bool = True, timeout: float | None = None) -> ty.Any:
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available.
        """
        if block:
            if timeout is None:
                # Blocking get with no timeout
                item = await self._client.brpop(self._name)
            else:
                # Blocking get with a timeout
                item = await self._client.brpop(self._name, timeout=timeout)
        else:
            item = await self._client.rpop(self._name)

        if item:
            # brpop returns a tuple (key, value), rpop returns just the value
            item_value = item[1] if isinstance(item, tuple) else item
            return json.loads(item_value)
        else:
            raise queue.Empty("No items in queue")
