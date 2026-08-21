import re

from typing import Dict, Any, Literal, List, Union, Awaitable, Callable, AsyncIterator

from pydantic import BaseModel, Field, field_validator

from mcp.schemas.common import Icon, Annotations
from mcp.schemas.resources import ResourceDataText, ResourceDataBinary
from chat.types import ChatToolFunction, ChatToolParameters, ChatToolParameterProperty


class MCPToolResultText(BaseModel):
    type: Literal["text"] = "text"
    text: str
    annotations: Annotations | None = None


class MCPToolResultImage(BaseModel):
    type: Literal["image"] = "image"
    data: str
    mimeType: str
    annotations: Annotations | None = None


class MCPToolResultAudio(BaseModel):
    type: Literal["audio"] = "audio"
    data: str
    mimeType: str
    annotations: Annotations | None = None


class MCPToolResultResource(BaseModel):
    type: Literal["resource"] = "resource"
    resource: Union[ResourceDataText, ResourceDataBinary]
    annotations: Annotations | None = None


class MCPToolResultResourceLink(BaseModel):
    type: Literal["resource_link"] = "resource_link"
    uri: str
    name: str
    description: str | None = None
    mimeType: str
    annotations: Annotations | None = None


MCPToolContent = Union[
    MCPToolResultText,
    MCPToolResultImage,
    MCPToolResultAudio,
    MCPToolResultResource,
    MCPToolResultResourceLink
]


class MCPToolDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    title: str | None = None
    description: str
    inputSchema: Dict[str, Any]
    outputSchema: Dict[str, Any] | None = None
    icons: List[Icon] | None = None

    @classmethod
    @field_validator('name')
    def validate_name(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_.-]+$', v):
            raise ValueError(f"Invalid tool name '{v}'")
        return v

    def to_chat_tool_function(self) -> "ChatToolFunction":
        """Convert this MCP tool definition into a chat tool function signature."""
        properties: Dict[str, ChatToolParameterProperty] = {}
        for name, prop in (self.inputSchema.get("properties") or {}).items():
            if not isinstance(prop, dict):
                prop = {}
            properties[name] = ChatToolParameterProperty(
                type=prop.get("type", "string"),
                description=prop.get("description", ""),
                format=prop.get("format"),
                enum=prop.get("enum"),
            )

        parameters = ChatToolParameters(
            properties=properties,
            required=list(self.inputSchema.get("required") or []),
            additionalProperties=bool(
                self.inputSchema.get("additionalProperties", False)
            ),
        )
        return ChatToolFunction(
            name=self.name,
            description=self.description,
            parameters=parameters,
        )


class MCPCallToolParams(BaseModel):
    name: str
    arguments: Dict[str, Any]


class MCPToolsCallResult(BaseModel):
    content: List[MCPToolContent] = Field(default_factory=list)
    structuredContent: Dict[str, Any] | None = None
    isError: bool = False


class MCPToolsListResponseResult(BaseModel):
    tools: List[MCPToolDefinition]
    nextCursor: str | None = None


class MCPToolsResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Union[MCPToolsListResponseResult, MCPToolsCallResult]


class MCPToolsChangedNotification(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["notifications/tools/list_changed"] = "notifications/tools/list_changed"


class MCPToolProgress(BaseModel):
    progress: float = Field(..., ge=0.0)
    total: float | None = Field(default=None, ge=0.0)
    message: str | None = None


class MCPToolResult(BaseModel):
    content: List[MCPToolContent]
    structuredContent: Dict[str, Any] | None = None
    isError: bool = False


class MCPTool(BaseModel):
    """
    Server-side representation of a registered tool.
    """
    func: Callable[
        [Dict[str, Any]],
        Union[
            Awaitable[MCPToolResult],
            AsyncIterator[Union[MCPToolProgress, MCPToolResult]]
        ]
    ]
    definition: MCPToolDefinition
    timeout: int = 60
