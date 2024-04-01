# PyThrottler

an intuitive throttler supports various backends and throttling algorihms

## Usage

1; decorate functions to be throttled

```python
from pythrottler import limits, throttler, ThrottleAlgo

@limits(quota=quota, duration_s=5, algo=ThrottleAlgo.FIX_WINDOW)
def add(a: int, b: int) -> int:
    res = a + b
    return res
```

## Install

```bash
pip install pythrottler
```

2; config throttler when app starts

```python
redis = Redis.from_url("redis://@127.0.0.1:6379/0")
throttler.config(quota_counter=RedisCounter(redis=redis))
```

## Supported Backend

| backend | supported|
| - | - |
| redis | True|
| memory | True|

## Supported Algorithms

| algorithm | supported |
| - | -|
| fixed window | True |
| sliding window | True |
| leaky bucket | True |
| token bucket | True |

## requirements

python >= 3.10
redis >= 5.0.3
