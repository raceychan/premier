# PyThrottler

pythrottler is an intuitive throttler that supports various backends and throttling algorihms, it can be used in distributed application for throttling web-api and any regular function.

- [PyThrottler](#pythrottler)
  - [Feature](#feature)
  - [Usage](#usage)
  - [Install](#install)
  - [Advanced Usage](#advanced-usage)
    - [Keyspace](#keyspace)
  - [Supported Backend](#supported-backend)
  - [Supported Algorithms](#supported-algorithms)
  - [requirements](#requirements)

## Feature

- Distributed throttling via redis or other backend.
- Support asyncio mode
- Support various throttling algorithms
- Designed to be highly customizable and extensible.

## Usage

1; decorate functions to be throttled

```python
from pythrottler import limits, throttler, ThrottleAlgo

@limits(quota=quota, duration_s=5, algo=ThrottleAlgo.FIX_WINDOW)
def add(a: int, b: int) -> int:
    res = a + b
    return res
```

2; config throttler when app starts

```python
redis = Redis.from_url("redis://@127.0.0.1:6379/0")
throttler.config(
    quota_counter=RedisCounter(redis=redis, ex_s=15), # set key expirey to 15 seconds
    algo=ThrottleAlgo.FIXED_WINDOW,# use fix window as the default throttling algorithm
    keyspace="pythrottler", # set pythrottler as the keyspace
)

```

## Install

```bash
pip install pythrottler
```

## Advanced Usage

### Keyspace

by default, pythrottler creates keyspace of this format for throttled functions

{keyspace}:{module}:{funcname}:{algorithm}

| name | explain | default |
| -  | -  | -|
| keyspace | customized string provided by user | "" |
| module | module name where function is defined in | func.\_\_module__ |
| funcname | name of the function | func.\_\_name__ |
| algorithm | throttling algorithm of the function | fixed_window |



## Supported Backend

| backend | sync | async |
| - | - | - |
| redis | supported | supported |
| memory | supported | supported |

## Supported Algorithms

| algorithm | status |
| - | -|
| fixed window | supported |
| sliding window | supported |
| leaky bucket | supported |
| token bucket | supported |

## requirements

python >= 3.10
redis >= 5.0.3
