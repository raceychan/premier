import logging

# Create a logger
logger = logging.getLogger("prmeier")
logger.setLevel(logging.DEBUG)  # Set the minimum level of logs to capture

# Create handlers for both file and console
console_handler = logging.StreamHandler()

# Set logging levels for each handler
console_handler.setLevel(logging.DEBUG)  # Debug and above go to the console

# Create formatters and add them to the handlers
console_format = logging.Formatter(
    "%(name)s | %(levelname)s | %(asctime)s | %(message)s"
)

console_handler.setFormatter(console_format)

# Add handlers to the logger
logger.addHandler(console_handler)
