from typing import List, Literal, Union

from pydantic import BaseModel

from mcp.schemas.common import Icon, Annotations


class ResourceDefinition(BaseModel):
    """
    Represents a resource definition in 'resources/list'.
    """
    uri: str
    name: str
    title: str | None = None
    description: str | None = None
    mimeType: str | None = None
    size: int | None = None
    icons: List[Icon] | None = None
    annotations: Annotations | None = None

class ResourceTemplate(BaseModel):
    """
    Represents a template in 'resources/templates/list'.
    """
    uriTemplate: str
    name: str
    title: str | None = None
    description: str | None = None
    mimeType: str | None = None
    icons: List[Icon] | None = None
    annotations: Annotations | None = None


class ResourceDataText(BaseModel):
    uri: str
    mimeType: str
    text: str


class ResourceDataBinary(BaseModel):
    uri: str
    mimeType: str
    blob: str


class Resource(BaseModel):
    """Server-side internal representation."""
    definition: ResourceDefinition
    data: Union[ResourceDataText, ResourceDataBinary]


class ResourcesListResponseResult(BaseModel):
    resources: List[ResourceDefinition]
    nextCursor: str | None = None


class ResourcesReadResponseResult(BaseModel):
    contents: List[Union[ResourceDataText, ResourceDataBinary]]


class ResourcesTemplatesListResult(BaseModel):
    resourceTemplates: List[ResourceTemplate]


class ResourcesResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Union[
        ResourcesListResponseResult,
        ResourcesReadResponseResult,
        ResourcesTemplatesListResult
    ]


class ResourcesChangedNotification(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["notifications/resources/list_changed"] = "notifications/resources/list_changed"
