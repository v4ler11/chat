from typing import Literal, Dict, Any

from pydantic import BaseModel, model_validator


LOGGING_LEVELS = [
    "debug",
    "info",
    "notice",
    "warning",
    "error",
    "critical",
    "alert",
    "emergency",
]


class LoggingParams(BaseModel):
    level: str
    logger: str
    data: Dict[str, Any]

    @model_validator(mode="after")
    def validate_level(self, level):
        if level not in LOGGING_LEVELS:
            raise ValueError(f"Invalid logging level: {level}; must be one of {LOGGING_LEVELS}")
        return level


class LoggingResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["notifications/message"] = "notifications/message"
    params: LoggingParams
