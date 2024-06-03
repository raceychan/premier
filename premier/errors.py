class ThrottlerError(Exception): ...


class QuotaExceedsError(ThrottlerError):
    time_remains: float

    def __init__(self, quota: int, duration_s: int, time_remains: float):
        msg = f"You exceeds {quota} quota in {duration_s} seconds, available after {time_remains:.2f} s"
        self.time_remains = time_remains
        super().__init__(msg)

class QueueFullError(ThrottlerError):
    def __init__(self, msg: str=""):
        self.msg = msg

class BucketFullError(QuotaExceedsError):
    def __init__(self, msg: str):
        self.msg = msg


class UninitializedHandlerError(ThrottlerError): ...
