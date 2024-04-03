import inspect
import typing as ty

from premier._types import AnyAsyncFunc, AnyFunc, Duration, KeyMaker, P
from premier.throttle_algo import Bucket, ThrottleAlgo, func_keymaker
from premier.throttler import throttler


@ty.overload
def limits(
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
def limits(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: ty.Literal[ThrottleAlgo.LEAKY_BUCKET],
    keymaker: KeyMaker | None = None,
    bucket_size: int,
): ...


def limits(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: ThrottleAlgo | None = None,
    keymaker: KeyMaker | None = None,
    bucket_size: int | None = None,
):
    "Register the function to be throttled"

    return throttler.limits(
        quota=quota,
        duration_s=duration_s,
        algo=algo,
        keymaker=keymaker,
        bucket_size=bucket_size,
    )


def leaky_bucket(
    bucket_size: int, quota: int, duration_s: int, keymaker: KeyMaker | None = None
):
    return limits(
        bucket_size=bucket_size,
        quota=quota,
        duration_s=duration_s,
        algo=ThrottleAlgo.LEAKY_BUCKET,
        keymaker=keymaker,
    )


def fixed_window(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return limits(
        quota=quota,
        duration_s=duration_s,
        algo=ThrottleAlgo.FIXED_WINDOW,
        keymaker=keymaker,
    )


def sliding_window(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return limits(
        quota=quota,
        duration_s=duration_s,
        algo=ThrottleAlgo.SLIDING_WINDOW,
        keymaker=keymaker,
    )


def token_bucket(quota: int, duration_s: int, keymaker: KeyMaker | None = None):
    return limits(
        quota=quota,
        duration_s=duration_s,
        algo=ThrottleAlgo.TOKEN_BUCKET,
        keymaker=keymaker,
    )
