class PremierError(Exception): ...


class ArgumentMissingError(PremierError):
    def __init__(self, msg: str = ""):
        self.msg = msg


class UninitializedHandlerError(PremierError): ...


class QuotaExceedsError(PremierError):
    time_remains: float

    def __init__(self, quota: int, duration_s: int, time_remains: float):
        msg = f"You exceeds {quota} quota in {duration_s} seconds, available after {time_remains:.2f} s"
        self.time_remains = time_remains
        super().__init__(msg)
