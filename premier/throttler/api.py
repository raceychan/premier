from .interface import KeyMaker, ThrottleAlgo
from .throttler import Throttler

DEFAULT_THROTTLER = Throttler()


def fixed_window(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return DEFAULT_THROTTLER.throttle(
        quota=quota,
        duration=duration_s,
        throttle_algo=ThrottleAlgo.FIXED_WINDOW,
        keymaker=keymaker,
    )


def sliding_window(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return DEFAULT_THROTTLER.throttle(
        quota=quota,
        duration=duration_s,
        throttle_algo=ThrottleAlgo.SLIDING_WINDOW,
        keymaker=keymaker,
    )


def token_bucket(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return DEFAULT_THROTTLER.throttle(
        quota=quota,
        duration=duration_s,
        throttle_algo=ThrottleAlgo.TOKEN_BUCKET,
        keymaker=keymaker,
    )


def leaky_bucket(
    bucket_size: int, quota: int, duration_s: int, keymaker: KeyMaker | None = None
):
    return DEFAULT_THROTTLER.throttle(
        bucket_size=bucket_size,
        quota=quota,
        throttle_algo=ThrottleAlgo.LEAKY_BUCKET,
        duration=duration_s,
        keymaker=keymaker,
    )
