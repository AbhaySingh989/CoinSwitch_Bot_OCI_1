import asyncio
import logging
from app import App
from logger import setup_logger

# Setup the logger
setup_logger()

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    app = App()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(app.main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        loop.run_until_complete(app.shutdown("KeyboardInterrupt"))
    except Exception as e:
        logger.error(f"An unhandled error occurred: {e}")
        loop.run_until_complete(app.shutdown("Unhandled Exception"))
