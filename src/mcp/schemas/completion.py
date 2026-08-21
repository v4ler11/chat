from typing import Literal, List

from pydantic import BaseModel


class Completion(BaseModel):
    values: List[str]
    total: int
    hasMore: bool


class CompletionResponseResult(BaseModel):
    completion: Completion


class CompletionResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str
    result: CompletionResponseResult
