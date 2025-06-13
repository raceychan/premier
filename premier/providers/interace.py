import typing as ty
from typing import Protocol, runtime_checkable


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
