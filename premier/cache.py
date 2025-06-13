import inspect
from functools import wraps
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

from premier.providers.interace import AsyncCacheProvider

P = ParamSpec("P")
R = TypeVar("R")
KeyMaker = Callable[..., str]


def _make_cache_key(
    func: Callable,
    keyspace: str,
    args: tuple,
    kwargs: dict,
    cache_key: str | KeyMaker | None = None,
) -> str:
    """Generate cache key for function call"""
    if cache_key is None:
        # Default key generation: function name + args + kwargs
        func_name = f"{func.__module__}.{func.__name__}"
        args_str = "_".join(str(arg) for arg in args)
        kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_parts = [keyspace, func_name, args_str, kwargs_str]
        return ":".join(filter(None, key_parts))
    elif isinstance(cache_key, str):
        return f"{keyspace}:{cache_key}" if keyspace else cache_key
    else:
        # cache_key is a function
        user_key = cache_key(*args, **kwargs)
        return f"{keyspace}:{user_key}" if keyspace else user_key


class Cache:
    """
    Async-only cache decorator for caching function results
    """

    def __init__(
        self,
        cache_provider: AsyncCacheProvider,
        keyspace: str = "premier:cache",
    ):
        self._cache_provider = cache_provider
        self._keyspace = keyspace

    async def clear(self, keyspace: str | None = None):
        if keyspace is None:
            keyspace = self._keyspace
        await self._cache_provider.clear(keyspace)

    def cache(
        self,
        expire_s: int | None = None,
        cache_key: str | KeyMaker | None = None,
        encoder: Callable[[R], Any] | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, Awaitable[R | None]]]:
        """
        Cache decorator

        Args:
            expire_s: TTL in seconds (None means no expiration)
            cache_key: Either a string key or function that generates key from args/kwargs
            encoder: Function to encode the result before caching (optional)
        """

        def wrapper(func: Callable[P, R]) -> Callable[P, Awaitable[R | None]]:
            @wraps(func)
            async def ainner(*args: P.args, **kwargs: P.kwargs) -> R | None:

                # Generate cache key
                key = _make_cache_key(
                    func=func,
                    keyspace=self._keyspace,
                    args=args,
                    kwargs=kwargs,
                    cache_key=cache_key,
                )

                # Try to get from cache first
                cached_data = await self._cache_provider.get(key)
                if cached_data is not None:
                    # Cache hit - return the cached value
                    return cached_data

                # Cache miss, execute function
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Encode result if encoder provided
                cache_value = encoder(result) if encoder else result

                # Store in cache with TTL
                await self._cache_provider.set(key, cache_value, ex=expire_s)
                return result

            return ainner

        return wrapper
