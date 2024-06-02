import asyncio
import functools
import random
import typing as ty

Exc_Callback = ty.Callable[[Exception], None]


# def expo_backoff(
#     retry_on: type[Exception] = Exception,
#     exc_callback: Exc_Callback = lambda exc: None,
#     max_retries: int = 3,
# ) -> ty.Callable:
#     """
#     copy from openai https://github.com/openai/transformer-debugger/blob/main/neuron_explainer/api_client.py
#     Returns a decorator which retries the wrapped function as long as the specified retry_on
#     function returns True for the exception, applying exponential backoff with jitter after
#     failures, up to a retry limit.
#     """
#     init_delay_s = 1
#     max_delay_s = 10
#     backoff_multiplier = 2.0
#     jitter = 0.2

#     def decorate(f: ty.Callable):
#         @functools.wraps(f)
#         async def f_retry(self, *args, **kwargs):
#             delay_s = init_delay_s
#             for i in range(max_retries):
#                 try:
#                     return await f(self, *args, **kwargs)
#                 except Exception as err:
#                     if i == max_retries - 1:
#                         print(f"Exceeded max tries ({max_retries}) on HTTP request")
#                         raise
#                     if not retry_on(err):
#                         print("Unretryable error on HTTP request")
#                         raise
#                     jittered_delay = random.uniform(
#                         delay_s * (1 - jitter), delay_s * (1 + jitter)
#                     )
#                     await asyncio.sleep(jittered_delay)
#                     delay_s = min(delay_s * backoff_multiplier, max_delay_s)

#         return f_retry

#     return decorate
