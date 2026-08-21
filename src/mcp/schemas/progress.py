from typing import Literal, Union

from pydantic import BaseModel, Field


class ProgressNotificationParams(BaseModel):
    progressToken: Union[str, int]
    progress: float = Field(ge=0.0)
    total: float | None = None
    message: str | None = None


class ProgressNotification(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["notifications/progress"] = "notifications/progress"
    params: ProgressNotificationParams
