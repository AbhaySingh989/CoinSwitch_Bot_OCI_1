import logging
from logging.handlers import RotatingFileHandler
from config import LOG_FILE

def setup_logger():
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set the root logger level

    # Prevent noisy libraries from spamming the log
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Create handlers
    # Rotating file handler for app.log
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)

    # Add handler to the root logger
    logger.addHandler(file_handler)

    return logger
