import typing as ty

from premier.throttler.interface import Duration, KeyMaker, R, ThrottleAlgo
from premier.throttler.throttler import throttler


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
) -> ty.Callable[[ty.Callable[..., R]], ty.Callable[..., R]]:
    pass


@ty.overload
def throttled(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: ty.Literal[ThrottleAlgo.LEAKY_BUCKET],
    keymaker: KeyMaker | None = None,
    bucket_size: int,
) -> ty.Callable[[ty.Callable[..., None]], ty.Callable[..., None]]: ...


def throttled(
    quota: int,
    duration_s: int | Duration,
    *,
    algo: ThrottleAlgo | None = None,
    keymaker: KeyMaker | None = None,
    bucket_size: int | None = None,
) -> (
    ty.Callable[[ty.Callable[..., None]], ty.Callable[..., None]]
    | ty.Callable[[ty.Callable[..., R]], ty.Callable[..., R]]
):
    "Register the function to be throttled"
    duration = (
        duration_s.as_seconds() if isinstance(duration_s, Duration) else duration_s
    )
    algo = algo or throttler.default_algo
    if algo is ThrottleAlgo.LEAKY_BUCKET:
        if bucket_size is None:
            raise ArgumentMissingError("bucket_size must be specified for LEAKY_BUCKET")
        return throttler.throttle(
            quota=quota,
            duration=duration,
            throttle_algo=algo,
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
    return throttler.throttle(
        bucket_size=bucket_size,
        quota=quota,
        throttle_algo=ThrottleAlgo.LEAKY_BUCKET,
        duration=duration_s,
        keymaker=keymaker,
    )
