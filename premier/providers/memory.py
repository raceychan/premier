import asyncio
import time
from typing import Any, Dict, Generic, TypeVar

from .interace import AsyncCacheProvider

T = TypeVar("T")


class AsyncInMemoryCache:
    def __init__(self, timer_func=time.time):
        self._storage: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._timer_func = timer_func
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any:
        async with self._lock:
            # Check if key has expired
            if key in self._expiry:
                if self._timer_func() > self._expiry[key]:
                    # Key has expired, remove it
                    self._storage.pop(key, None)
                    self._expiry.pop(key, None)
                    return None
            return self._storage.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        async with self._lock:
            self._storage[key] = value
            if ex is not None:
                self._expiry[key] = self._timer_func() + ex
            else:
                # Remove expiry if it exists
                self._expiry.pop(key, None)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._storage.pop(key, None)
            self._expiry.pop(key, None)

    async def clear(self, keyspace: str = "") -> None:
        async with self._lock:
            if not keyspace:
                self._storage.clear()
                self._expiry.clear()
            else:
                keys = [k for k in self._storage if k.startswith(keyspace)]
                for k in keys:
                    self._storage.pop(k, None)
                    self._expiry.pop(k, None)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            # Check if key has expired first
            if key in self._expiry:
                if self._timer_func() > self._expiry[key]:
                    # Key has expired, remove it
                    self._storage.pop(key, None)
                    self._expiry.pop(key, None)
                    return False
            return key in self._storage

    async def close(self) -> None:
        pass


class AsyncInMemoryQueue(Generic[T]):
    def __init__(self, maxsize: int):
        self._maxsize = maxsize
        self._queue = asyncio.Queue[T](maxsize=maxsize)

    async def put(self, item: T) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            from premier.throttler.errors import QueueFullError
            raise QueueFullError("Queue is full. Cannot add more items.")

    async def get(self, block: bool = True, *, timeout: float = 0) -> T | None:
        if not block:
            try:
                return self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
        
        try:
            if timeout > 0:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                return await self._queue.get()
        except asyncio.TimeoutError:
            return None

    async def qsize(self) -> int:
        return self._queue.qsize()

    async def empty(self) -> bool:
        return self._queue.empty()

    async def full(self) -> bool:
        return self._queue.full()

    @property
    def capacity(self) -> int:
        return self._maxsize

    async def clear(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def close(self) -> None:
        pass
