from typing import Any, Dict, Literal, Union
from pydantic import BaseModel, model_serializer


INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
PARSE_ERROR = -32700

RESOURCE_NOT_FOUND = -32002


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Dict[str, Any] | None = None
    id: Union[str, int] | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int] | None = None
    result: Any | None = None
    error: Dict[str, Any] | None = None


class ServerCapabilities(BaseModel):
    logging: Dict[str, Any] | None = None
    prompts: Dict[str, Any]
    resources: Dict[str, Any]
    tools: Dict[str, Any]

    @classmethod
    def new(cls) -> "ServerCapabilities":
        return cls(
            # logging=dict(), # todo: implement logging
            prompts=dict(
                listChanged=True
            ),
            resources=dict(
                subscribe=True,
                listChanged=True,
            ),
            tools=dict(
                listChanged=True
            )
        )


class ServerInfo(BaseModel):
    name: str
    version: str


class JsonRpcResponseInitializeResult(BaseModel):
    protocolVersion: str = "2025-11-25"
    capabilities: ServerCapabilities
    serverInfo: ServerInfo
    instructions: str | None = None

    @classmethod
    def new(cls, name: str, version: str) -> "JsonRpcResponseInitializeResult":
        return cls(
            capabilities=ServerCapabilities.new(),
            serverInfo=ServerInfo(name=name, version=version),
        )


class JsonRpcError(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    code: int
    message: str
    data: Any | None = None

    @model_serializer
    def serialize(self) -> Dict[str, Any]:
        error_obj = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            error_obj["data"] = self.data

        return {
            "jsonrpc": self.jsonrpc,
            "error": error_obj,
            "id": self.id
        }
