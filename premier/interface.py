from typing import Awaitable, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

SimpleDecor = Callable[P, R]
ParamDecor = Callable[[Callable[P, R]], Callable[P, R]]
AsyncSimpleDecor = Callable[P, Awaitable[R]]
AsyncParamDecor = Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]
FlexDecor = (
    SimpleDecor[P, R]
    | ParamDecor[P, R]
    | AsyncSimpleDecor[P, R]
    | AsyncParamDecor[P, R]
)
