from typing import Callable, Protocol


class ILogger(Protocol):
    def exception(self, msg: str): ...

    def info(self, msg: str): ...


CustomLogger = Callable[[float], None]

ValidLogger = ILogger | CustomLogger
