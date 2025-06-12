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

@throttler.fixed_window(quota=3, duration=5)
def request(url: str) -> str:
    r = httpx.get(url)
    return r.text

@throttler.token_bucket(quota=3, duration=5)
async def async_request(client: httpx.AsyncClient, url: str) -> str:
  r = await client.get('https://www.example.com/')
  return r.text
```

- config throttler as your app starts

```python
from redis import Redis
from redis.asyncio.client import Redis as AIORedis
from premier.providers.redis import AsyncRedisCacheAdapter

REDIS_URL = "redis://@127.0.0.1:6379/0"
aredis = AsyncRedisCacheAdapter(AIORedis.from_url(REDIS_URL)) 

throttler = Throttler(
    handler = AsyncRedisHandler(aredis), # only if you need to throttle async functions
    algo=ThrottleAlgo.FIXED_WINDOW, # use fix window as the default throttling algorithm
    keyspace="premier:throttler", # set premier as the keyspace
)
```

- use in lihil

checkout [lihil-plugins](https://www.lihil.cc/docs/advance/plugin) for details

## Install

```bash
pip install premier
```

## Advanced Usage

### Keyspace

by default, premier creates keyspace of this format for throttled functions

{keyspace}:{module}:{funcname}:{algorithm}

| name      | explain                                  | default             |
| --------- | ---------------------------------------- | ------------------- |
| keyspace  | customized string provided by user       | "premier"           |
| module    | module name where function is defined in | func.\_\_module\_\_ |
| funcname  | name of the function                     | func.\_\_name\_\_   |
| algorithm | throttling algorithm of the function     | fixed_window        |

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

| backend | sync      | async     |
| ------- | --------- | --------- |
| redis   | supported | supported |
| memory  | supported | supported |

## Supported Algorithms

| algorithm      | status    |
| -------------- | --------- |
| fixed window   | supported |
| sliding window | supported |
| leaky bucket   | supported |
| token bucket   | supported |

## requirements

- python >= 3.10

[optional]
- redis >= 5.0.3

## DevPlan


- [x] implement timeout feature
- [x] implement retry feature
- [x] implement cache feature
