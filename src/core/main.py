
from loguru import logger

import core.logger
import core.traces


def main():
    logger.info("Logger initialized")

    try:
        pass

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt")
    finally:
        logger.info("Otel - Shutdown")
        core.traces.shutdown()

    exit(0)
