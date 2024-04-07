import typing as ty
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto

# from concurrent.futures import Future

_K = ty.TypeVar("_K", bound=ty.Hashable)
_V = ty.TypeVar("_V")
T = ty.TypeVar("T")
P = ty.ParamSpec("P")
R = ty.TypeVar("R", covariant=True)


KeyMaker = ty.Callable[..., str]


@ty.runtime_checkable
class AnyAsyncFunc(ty.Protocol[P, R]):
    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


@ty.runtime_checkable
class AnyFunc(ty.Protocol[P, R]):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...

class QuotaCounter(ty.Generic[_K, _V], ABC):
    """
    TODO: implemetn algorithm in counter
    """
    @abstractmethod
    def get(self, key: _K, default: T) -> _V | T:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: _K, value: _V) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self, keyspace: str = "") -> None:
        raise NotImplementedError

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class ThrottleData:
    func: ... 
    algo: "ThrottleAlgo"
    quota: int
    duration: int
    bucket_size: int



class ThrottleHandler:
    def __init__(self, counter):
        self._counter = counter

    def throttle(self, key: str):
        ...

class LeakyBucketHandler(ThrottleHandler):
    def __init__(self, counter):
        super().__init__(counter)
        self.lock = threading.Lock()
        self.waiting_tasks = deque()

    def throttle(self, key: str):
        ...

    def schedule_task(self, func, args, kwargs):
        res = func(args, kwargs)
        return res

    def dispatch(self, throttle_data: ThrottleData):
        match throttle_data.algo:
            case ThrottleAlgo.LEAKY_BUCKET:
                ...

"""
with throttler.acquire():
    future = throttle.schedule_task(func, args, kwargs)

@retry(max=3, on_exception=(QuotaExceeds, TimeOutError), retry_after=retry_after_waittime)
@throttler.leaky_bucket
@timeout(max=60s, raise=TimeoutError)
@cache
def add(a, b):
    return a + b

"""



class AsyncQuotaCounter(ty.Generic[_K, _V], QuotaCounter[_K, _V]):
    @abstractmethod
    async def get(self, key: _K, default: T) -> _V | T:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: _K, value: _V) -> None:
        raise NotImplementedError

    @abstractmethod
    async def clear(self, keyspace: str = "") -> None:
        raise NotImplementedError


class Algorithm(ABC):
    @abstractmethod
    def get_token(
        self, key: ty.Hashable, quota: int, duration: int
    ) -> ty.Literal[-1] | float:
        raise NotImplementedError


@dataclass(kw_only=True)
class Duration:
    seconds: int
    minutes: int
    hours: int
    days: int

    @classmethod
    def from_seconds(cls, seconds: int):
        total = seconds
        d = h = m = 0

        while total >= 86400:
            d += 1
            total -= 86400

        while total >= 3600:
            h += 1
            total -= 3600

        while total >= 60:
            m += 1
            total -= 60
        return cls(seconds=total, minutes=m, hours=h, days=d)

    def as_seconds(self):
        total = (
            (self.days * 86400)
            + (self.hours * 3600)
            + (self.minutes * 60)
            + self.seconds
        )
        return total


class AlgoTypeEnum(Enum):
    def _generate_next_value_(name: str, _, __, ___):
        return name.lower()  # type: ignore


class ThrottleAlgo(str, AlgoTypeEnum):
    TOKEN_BUCKET = auto()
    LEAKY_BUCKET = auto()
    FIXED_WINDOW = auto()
    SLIDING_WINDOW = auto()


class ThrottleInfo(ty.NamedTuple):
    funckey: str
    quota: int
    duration: Duration
    algorithm: ThrottleAlgo
