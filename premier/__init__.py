import sys

from ._types import ThrottleAlgo as ThrottleAlgo
from .api import fixed_window as fixed_window
from .api import leaky_bucket as leaky_bucket
from .api import sliding_window as sliding_window
from .api import throttled as throttled
from .api import token_bucket as token_bucket
from .errors import QuotaExceedsError as QuotaExceedsError
from .handler import AsyncDefaultHandler as AsyncDefaultHandler
from .handler import AsyncRedisHandler as AsyncRedisHandler
from .handler import BucketFullError as BucketFullError
from .handler import DefaultHandler as DefaultHandler
from .handler import RedisHandler as RedisHandler
from .throttler import Throttler as Throttler
from .throttler import throttler as throttler

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata


def int_or_str(value: str):
    try:
        return int(value)
    except ValueError:
        return value


__version__ = "0.3.0"


VERSION = tuple(int_or_str(x) for x in __version__.split("."))
