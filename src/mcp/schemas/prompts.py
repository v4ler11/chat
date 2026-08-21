from typing import List, Literal, Dict, Any, Union, Awaitable, Callable

from pydantic import BaseModel, Field

from mcp.schemas.common import Icon
from mcp.schemas.resources import ResourceDataText, ResourceDataBinary


class PromptArgument(BaseModel):
    name: str
    description: str | None = None
    required: bool


class PromptDefinition(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    arguments: List[PromptArgument] = Field(default_factory=list)
    icons: List[Icon] | None = None


class PromptsListResponseResult(BaseModel):
    prompts: List[PromptDefinition]
    nextCursor: str | None = None


class PromptMessageContentText(BaseModel):
    type: Literal["text"] = "text"
    text: str


class PromptMessageContentImage(BaseModel):
    type: Literal["image"] = "image"
    data: str
    mimeType: str


class PromptMessageContentAudio(BaseModel):
    type: Literal["audio"] = "audio"
    data: str
    mimeType: str


class PromptMessageContentResource(BaseModel):
    type: Literal["resource"] = "resource"
    resource: Union[ResourceDataText, ResourceDataBinary]


class PromptMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: Union[
        PromptMessageContentText,
        PromptMessageContentImage,
        PromptMessageContentAudio,
        PromptMessageContentResource
    ]


class PromptsGetResult(BaseModel):
    description: str | None = None
    messages: List[PromptMessage]


class Prompt(BaseModel):
    """Server-side internal representation."""
    func: Callable[[Dict[str, Any]], Awaitable[PromptsGetResult]]
    definition: PromptDefinition
    timeout: int = 3


class PromptsResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Union[PromptsListResponseResult, PromptsGetResult]


class PromptsChangedResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["notifications/prompts/list_changed"] = "notifications/prompts/list_changed"
