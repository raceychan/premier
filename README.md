# premier

premier is an intuitive throttler that supports various backends and throttling algorihms, it can be used in distributed application for throttling web-api and any regular function.

- [premier](#premier)
  - [Feature](#feature)
  - [Usage](#usage)
  - [Install](#install)
  - [Advanced Usage](#advanced-usage)
    - [Keyspace](#keyspace)
    - [Customized throttle key](#customized-throttle-key)
  - [Supported Backend](#supported-backend)
  - [Supported Algorithms](#supported-algorithms)
  - [requirements](#requirements)
  - [DevPlan](#devplan)

## Feature

- Distributed throttling via redis or other backend.
- Support asyncio mode
- Support various throttling algorithms
- Designed to be highly customizable and extensible.

## Usage

1. decorate functions to be throttled

```python
from premier import limits, throttler, ThrottleAlgo

@throttler.fixed_window(quota=quota, duration_s=5, algo=ThrottleAlgo.FIXED_WINDOW)
def add(a: int, b: int) -> int:
    res = a + b
    return res
```

2. config throttler when app starts

```python
redis = Redis.from_url("redis://@127.0.0.1:6379/0")
throttler.config(
    quota_counter=RedisCounter(redis=redis, ex_s=15), # set key expirey to 15 seconds
    algo=ThrottleAlgo.FIXED_WINDOW,# use fix window as the default throttling algorithm
    keyspace="premier", # set premier as the keyspace
)

```

## Install

```bash
pip install premier
```

## Advanced Usage

### Keyspace

by default, premier creates keyspace of this format for throttled functions

{keyspace}:{module}:{funcname}:{algorithm}

| name | explain | default |
| -  | -  | -|
| keyspace | customized string provided by user | "premier" |
| module | module name where function is defined in | func.\_\_module__ |
| funcname | name of the function | func.\_\_name__ |
| algorithm | throttling algorithm of the function | fixed_window |

### Customized throttle key

You might provide your own keymaker to the 'throttler' function like this

```python
from premier import throttler

@throttler.fixed_window(quota=3, duration_s=5, keymaker=lambda a, b: f"{a}")
def add(a: int, b: int) -> int:
    res = a + b
    return res
```

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

- python >= 3.10
- redis >= 5.0.3

## DevPlan

TODO:


- [x] implement timeout feature
- [ ] implement retry feature
- [ ] implement cache feature

API Design:

```python
type Strategy = ty.Callable[[int], float]

@cache
@retry(strategy="expo", max=3, on_exception=(TimeOut, QuotaExceeds))
@timeout(60)
@throttler.leaky_bucket
def add(a:int, b:int):
    return a + b
```
