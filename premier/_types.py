import typing as ty
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto

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
    @abstractmethod
    def get(self, key: _K, default: T) -> _V | T:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: _K, value: _V) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self, keyspace: str = "") -> None:
        raise NotImplementedError


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
