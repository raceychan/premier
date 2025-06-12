from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from types import FunctionType, MethodType
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Literal,
    ParamSpec,
    Protocol,
    Sequence,
    TypeVar,
)

KeyMaker = Callable[..., str]
CountDown = Literal[-1] | float


KeysT = TypeVar("KeysT", bound=Sequence[bytes | str | memoryview], contravariant=True)
ArgsT = TypeVar(
    "ArgsT",
    bound=Iterable[str | int | float | bytes | memoryview],
    contravariant=True,
)
ResultT = TypeVar("ResultT", bound=Any, covariant=True)
AsyncTaskScheduler = Callable[..., Awaitable[None]]


T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R", covariant=True)
QueueItem = TypeVar("QueueItem")


def func_keymaker(func: Callable[..., Any], algo: "ThrottleAlgo", keyspace: str):
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


def make_key(
    func: Callable[..., Any],
    algo: "ThrottleAlgo",
    keyspace: str,
    keymaker: KeyMaker | None,
    args: tuple[object, ...],
    kwargs: dict[Any, Any],
) -> str:
    key = func_keymaker(func, algo, keyspace)
    if not keymaker:
        return key
    return f"{key}:{keymaker(*args, **kwargs)}"




class AsyncTaskQueue(Protocol, Generic[QueueItem]):
    async def put(self, item: QueueItem) -> None: ...
    async def get(self, block: bool = True, *, timeout: float = 0) -> QueueItem: ...
    async def qsize(self) -> int: ...
    async def empty(self) -> bool: ...
    async def full(self) -> bool: ...
    @property
    @abstractmethod
    def capacity(self) -> int: ...




class SyncFunc(Protocol[P, R]):
    __name__: str

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


class AsyncFunc(Protocol[P, R]):
    __name__: str

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


class ScriptFunc(Protocol, Generic[KeysT, ArgsT, ResultT]):
    def __call__(self, keys: KeysT, args: ArgsT) -> ResultT:
        raise NotImplementedError


@dataclass(frozen=True, slots=True, kw_only=True)
class ThrottleInfo:
    func: Callable[..., Any]
    keyspace: str
    algo: "ThrottleAlgo"

    @property
    def funckey(self):
        return func_keymaker(self.func, self.algo, self.keyspace)

    def make_key(
        self,
        keymaker: KeyMaker | None,
        args: tuple[object, ...],
        kwargs: dict[Any, Any],
    ) -> str:
        key = self.funckey
        if not keymaker:
            return key

        return f"{key}:{keymaker(*args, **kwargs)}"


@dataclass(frozen=True, slots=True, kw_only=True)
class LBThrottleInfo(ThrottleInfo):
    bucket_size: int


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
    def _generate_next_value_(name: str, _start: int, _count: int, _last_values: list[Any]):
        return name.lower()  # type: ignore


class ThrottleAlgo(str, AlgoTypeEnum):
    TOKEN_BUCKET = auto()
    LEAKY_BUCKET = auto()
    FIXED_WINDOW = auto()
    SLIDING_WINDOW = auto()




class AsyncThrottleHandler(ABC):

    @abstractmethod
    async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        pass

    @abstractmethod
    async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        pass

    @abstractmethod
    async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        pass

    @abstractmethod
    def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> AsyncTaskScheduler: ...

    @abstractmethod
    async def clear(self, keyspace: str = "") -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    def dispatch(self, algo: ThrottleAlgo):
        "does not handle the leaky bucket case"
        match algo:
            case ThrottleAlgo.FIXED_WINDOW:
                return self.fixed_window
            case ThrottleAlgo.SLIDING_WINDOW:
                return self.sliding_window
            case ThrottleAlgo.TOKEN_BUCKET:
                return self.token_bucket
            case _:
                raise NotImplementedError
