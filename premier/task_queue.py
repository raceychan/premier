import json
import queue
import typing as ty
from asyncio import Lock as AsyncLock
from threading import Lock

from redis.asyncio.client import Redis as AIORedis
from redis.client import Redis  # type: ignore

from premier._types import AsyncTaskQueue, QueueItem, TaskQueue
from premier.errors import QueueFullError


def json_loads(data: bytes) -> ty.Any:
    res = json.loads(data.decode("utf-8"))
    return res


def json_dumps(data: ty.Any) -> bytes:
    res = json.dumps(data).encode("utf-8")
    return res


class IQueue(TaskQueue[QueueItem]):
    def __init__(self, maxsize: int):
        self._size = maxsize
        self._queue = queue.Queue[QueueItem](maxsize=maxsize)

    @property
    def capacity(self) -> int:
        return self._size

    def put(self, item: QueueItem) -> None:
        try:
            self._queue.put(item, block=False)
        except queue.Full:
            raise QueueFullError

    def get(self, block: bool = True, *, timeout: float = 0) -> QueueItem:
        return self._queue.get(block=block, timeout=timeout)

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()

    def full(self) -> bool:
        return self._queue.full()


class RedisQueue(TaskQueue[QueueItem]):
    def __init__(self, client: Redis, *, name: str, queue_size: int):
        self._client = client
        self._name = name
        self._size = queue_size
        self.__lock = Lock()

    def qsize(self) -> int:
        """Return the approximate size of the queue."""
        size = self._client.llen(self._name)
        return size  # type: ignore

    def empty(self) -> bool:
        """Return True if the queue is empty, False otherwise."""
        return self.qsize() == 0

    @property
    def capacity(self) -> int:
        return self._size

    def full(self) -> bool:
        return self.qsize() >= self._size

    def get(self, block: bool = True, *, timeout: float = 0) -> QueueItem:
        """Remove and return an item from the queue.
        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available.
        """
        item: list[ty.Any] | None
        if block:
            key, item = self._client.brpop([self._name], timeout=timeout)  # type: ignore
        else:
            item = self._client.rpop(self._name)  # type: ignore

        return json_loads(item) if item else None  # type: ignore

    def put(self, item: QueueItem) -> None:
        """Put an item into the queue."""
        item_bytes = json_dumps(item)
        with self.__lock:
            if self.full():
                raise QueueFullError("Bucket is full. Cannot add more items.")
            self._client.lpush(self._name, item_bytes)

    def clear(self) -> None:
        """Clear all items from the queue."""
        self._client.delete(self._name)  # type: ignore

    def close(self) -> None:
        """Close the Redis connection."""
        self._client.close()

    def __del__(self):
        self.close()


class AsyncRedisQueue(AsyncTaskQueue[QueueItem]):
    def __init__(self, client: AIORedis, *, name: str, queue_size: int):
        self._client = client
        self._name = name
        self._size = queue_size
        self.__lock = AsyncLock()

    @property
    def capacity(self) -> int:
        return self._size

    async def qsize(self) -> int:
        """Return the approximate size of the queue."""
        size = await self._client.llen(self._name)  # type: ignore
        return size  # type: ignore

    async def empty(self) -> bool:
        """Return True if the queue is empty, False otherwise."""
        return await self.qsize() == 0

    async def get(self, block: bool = True, *, timeout: float = 0) -> QueueItem:
        """Remove and return an item from the queue.
        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available.
        """

        if block:
            key, item = await self._client.brpop(self._name, timeout=timeout)  # type: ignore
        else:
            item = await self._client.rpop(self._name)  # type: ignore

        return json_loads(item) if item else None  # type: ignore

    async def put(self, item: QueueItem) -> None:
        """Put an item into the queue."""
        item_bytes = json_dumps(item)
        async with self.__lock:
            if await self.full():
                raise QueueFullError("Bucket is full. Cannot add more items.")
            await self._client.lpush(self._name, item_bytes)  # type: ignore

    async def full(self) -> bool:
        return await self.qsize() >= self._size
