import typing as ty

from premier._types import Duration, KeyMaker
from premier.throttle_algo import ThrottleAlgo
from premier.throttler import throttler


@ty.overload
def throttled(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: (
        ty.Literal[ThrottleAlgo.FIXED_WINDOW]
        | ty.Literal[ThrottleAlgo.SLIDING_WINDOW]
        | ty.Literal[ThrottleAlgo.TOKEN_BUCKET]
        | None
    ) = None,
    keymaker: KeyMaker | None = None,
    bucket_size: None = None,
): ...


# Overload specifically for the LEAKY_BUCKET algorithm, requiring bucket_size
@ty.overload
def throttled(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: ty.Literal[ThrottleAlgo.LEAKY_BUCKET],
    keymaker: KeyMaker | None = None,
    bucket_size: int,
): ...


def throttled(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: ThrottleAlgo | None = None,
    keymaker: KeyMaker | None = None,
    bucket_size: int | None = None,
):
    "Register the function to be throttled"
    duration = (
        duration_s.as_seconds() if isinstance(duration_s, Duration) else duration_s
    )
    algo = algo or throttler.default_algo
    if algo is ThrottleAlgo.LEAKY_BUCKET:
        assert bucket_size
        return throttler.leaky_bucket(
            quota=quota,
            duration_s=duration,
            keymaker=keymaker,
            bucket_size=bucket_size,
        )

    return throttler.throttle(
        quota=quota,
        duration=duration,
        throttle_algo=algo,
        keymaker=keymaker,
    )


def fixed_window(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return throttler.throttle(
        quota=quota,
        duration=duration_s,
        throttle_algo=ThrottleAlgo.FIXED_WINDOW,
        keymaker=keymaker,
    )


def sliding_window(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return throttler.throttle(
        quota=quota,
        duration=duration_s,
        throttle_algo=ThrottleAlgo.SLIDING_WINDOW,
        keymaker=keymaker,
    )


def token_bucket(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return throttler.throttle(
        quota=quota,
        duration=duration_s,
        throttle_algo=ThrottleAlgo.TOKEN_BUCKET,
        keymaker=keymaker,
    )


def leaky_bucket(
    bucket_size: int, quota: int, duration_s: int, keymaker: KeyMaker | None = None
):
    return throttler.leaky_bucket(
        bucket_size=bucket_size,
        quota=quota,
        duration_s=duration_s,
        keymaker=keymaker,
    )
