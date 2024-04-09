import threading
import typing as ty
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from types import FunctionType, MethodType

# from concurrent.futures import Future

_K = ty.TypeVar("_K", bound=ty.Hashable)
_V = ty.TypeVar("_V")
T = ty.TypeVar("T")
P = ty.ParamSpec("P")
R = ty.TypeVar("R", covariant=True)


KeyMaker = ty.Callable[..., str]
CountDown = ty.Literal[-1] | float


@ty.runtime_checkable
class AsyncFunc(ty.Protocol[P, R]):
    __name__: str

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


@ty.runtime_checkable
class SyncFunc(ty.Protocol[P, R]):
    __name__: str

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


AnySyncFunc = SyncFunc[..., ty.Any]
AnyAsyncFunc = AsyncFunc[..., ty.Any]


def func_keymaker(
    func: AnySyncFunc | AnyAsyncFunc, algo: "ThrottleAlgo", keyspace: str
):
    if isinstance(func, MethodType):
        # It's a method, get its class name and method name
        class_name = func.__self__.__class__.__name__
        func_name = func.__name__
        fid = f"{class_name}:{func_name}"
    elif isinstance(func, FunctionType):
        # It's a standalone function
        fid = func.__name__
    else:
        try:
            fid = func.__name__
        except AttributeError:
            fid = ""

    return f"{keyspace}:{algo.value}:{func.__module__}:{fid}"


@dataclass(frozen=True, slots=True, kw_only=True)
class ThrottleInfo:
    func: AnySyncFunc | AnyAsyncFunc
    keyspace: str
    algo: "ThrottleAlgo"

    @property
    def funckey(self):
        return func_keymaker(self.func, self.algo, self.keyspace)

    def make_key(
        self,
        keymaker: KeyMaker | None,
        args: tuple[object, ...],
        kwargs: dict[ty.Any, ty.Any],
    ) -> str:
        key = self.funckey
        if not keymaker:
            return key

        return f"{key}:{keymaker(*args, **kwargs)}"


@dataclass(frozen=True, slots=True, kw_only=True)
class LBThrottleInfo(ThrottleInfo):
    bucket_size: int


class QuotaCounter(ty.Generic[_K, _V], ABC):
    """
    TODO: implement algorithm in counter
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


class AsyncQuotaCounter(ty.Generic[_K, _V]):
    @abstractmethod
    async def get(self, key: _K, default: T) -> _V | T:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: _K, value: _V) -> None:
        raise NotImplementedError

    @abstractmethod
    async def clear(self, keyspace: str = "") -> None:
        raise NotImplementedError


class ThrottleHandler(ABC):
    def __init__(
        self,
        counter: QuotaCounter[ty.Any, ty.Any],
        lock: threading.Lock,
        throttle_info: ThrottleInfo,
    ):
        self._counter = counter
        self._lock = lock
        self._info = throttle_info

    @abstractmethod
    def acquire(self, key: ty.Hashable, quota: int, duration: int) -> CountDown:
        pass


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
    @staticmethod
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[ty.Any]
    ):
        return name.lower()  # type: ignore


class ThrottleAlgo(str, AlgoTypeEnum):
    TOKEN_BUCKET = auto()
    LEAKY_BUCKET = auto()
    FIXED_WINDOW = auto()
    SLIDING_WINDOW = auto()
