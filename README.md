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

- decorate functions to be throttled

```python
import httpx
from premier import limits, throttler, ThrottleAlgo, RedisHandler

<<<<<<< HEAD
fixed_window = throttler.fixed_window(quota=3, duration=5, algo=ThrottleAlgo.FIXED_WINDOW)
=======
fixed_window = throttler.fixed_window(quota=3, duration=5)
>>>>>>> version/0.4.1

@fixed_window
def request(url: str) -> str:
    r = httpx.get(url)
    return r.text

@fixed_window
async def async_request(client: httpx.AsyncClient, url: str) -> str:
  r = await client.get('https://www.example.com/')
  return r.text
```

- config throttler as your app starts

```python
from redis import Redis
from redis.asyncio.client import Redis as AIORedis

REDIS_URL = "redis://@127.0.0.1:6379/0"
redis = Redis.from_url(REDIS_URL)
aredis = AIORedis.from_url(REDIS_URL) # only if you need to throttle async functions

throttler.config(
    handler = RedisHandler(redis=redis),
    aiohandler = AsyncRedisHandler(aredis), # only if you need to throttle async functions
    algo=ThrottleAlgo.FIXED_WINDOW, # use fix window as the default throttling algorithm
    keyspace="premier", # set premier as the keyspace
)
<<<<<<< HEAD
=======
```

- use in fastapi

```python
@app.get("/", dependencies=[Depends(throttler.get_countdown)])
async def index():
    return {"msg": "Hello World"}
>>>>>>> version/0.4.1
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

@throttler.fixed_window(quota=3, duration=5, keymaker=lambda a, b: f"{a}")
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
| - | - |
| fixed window | supported |
| sliding window | supported |
| leaky bucket | supported |
| token bucket | supported |

## requirements

- python >= 3.10
- redis >= 5.0.3

## DevPlan

TODO:

- [ ] support lowering version python by using type-extensions
- [ ] implement timeout feature
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