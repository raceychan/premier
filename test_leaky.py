from time import sleep

from premier import BucketFullError, leaky_bucket


def test():
    # Example usage
    @leaky_bucket(bucket_size=5, quota=1, duration_s=1, keymaker=None)
    def my_function(a: int, b: int, c: int):
        sleep(0.1)  # Simulate some work that takes time.
        return a + b

    # Test the throttling
    for i in range(8):
        try:
            my_function(i, i)
        except BucketFullError:
            print("bucekt is fucking full!")
