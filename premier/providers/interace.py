import typing as ty
from typing import Generic, Protocol, TypeVar, runtime_checkable


@runtime_checkable
class AsyncCacheProvider(Protocol):
    async def get(self, key: str) -> ty.Any:
        """Get value by key. Returns None if key doesn't exist."""
        ...

    async def set(self, key: str, value: ty.Any, ex: int | None = None) -> None:
        """Set key-value pair with optional expiration time in seconds."""
        ...

    async def delete(self, key: str) -> None:
        """Delete key."""
        ...

    async def clear(self, keyspace: str = "") -> None:
        """Clear all keys with the given prefix. If empty, clear all."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...

    async def close(self) -> None:
        """Close the cache provider."""
        ...


T = TypeVar("T")


@runtime_checkable
class AsyncQueueProvider(Protocol, Generic[T]):
    async def put(self, item: T) -> None:
        """Put an item into the queue."""
        ...

    async def get(self, block: bool = True, *, timeout: float = 0) -> T | None:
        """Get an item from the queue."""
        ...

    async def qsize(self) -> int:
        """Return the approximate size of the queue."""
        ...

    async def empty(self) -> bool:
        """Return True if the queue is empty."""
        ...

    async def full(self) -> bool:
        """Return True if the queue is full."""
        ...

    @property
    def capacity(self) -> int:
        """Return the maximum capacity of the queue."""
        ...

    async def clear(self) -> None:
        """Clear all items from the queue."""
        ...

    async def close(self) -> None:
        """Close the queue provider."""
        ...
