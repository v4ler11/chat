import sys

from loguru import logger

from core.globals import LOGS_DIR


logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

logger.add(
    f"{str(LOGS_DIR)}/{{time:YYYYMMDD}}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    encoding="utf-8"
)
