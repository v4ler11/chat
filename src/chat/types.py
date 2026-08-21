import secrets
import time

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ConfigDict


class Function(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str = Field(..., description="The ID of the tool call.")
    type: Literal["function"] = "function"
    function: Function


class ChatToolParameterProperty(BaseModel):
    type: str
    description: str = ""
    format: Optional[str] = None
    enum: Optional[List[str]] = None
    items: Optional["ChatToolParameterProperty"] = None
    properties: Optional[Dict[str, "ChatToolParameterProperty"]] = None
    required: Optional[List[str]] = None


class ChatToolParameters(BaseModel):
    type: Literal["object"] = "object"
    properties: Dict[str, ChatToolParameterProperty]
    required: List[str]
    additionalProperties: bool = False


class ChatToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    strict: bool = False
    parameters: ChatToolParameters


class ChatTool(BaseModel):
    type: Literal["function"] = "function"
    function: ChatToolFunction


class ChatMessageBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    content: Any | None


class ChatMessageSystem(ChatMessageBase):
    role: Literal["system"] = "system"
    content: str


class ChatMessageUser(ChatMessageBase):
    role: Literal["user"] = "user"
    content: str


class ChatMessageTool(ChatMessageBase):
    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str


class ChatMessageAssistant(ChatMessageBase):
    role: Literal["assistant"] = "assistant"
    content: str | None

    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


ChatMessage = Union[ChatMessageSystem, ChatMessageUser, ChatMessageAssistant, ChatMessageTool]


class ChatDelta(BaseModel):
    role: Optional[Literal["assistant", "system"]] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    audio: Optional[Any] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChoiceBase(BaseModel):
    index: int = 0
    logprobs: Optional[Any] = None
    finish_reason: Optional[str] = None


class ChoiceNonStreaming(ChoiceBase):
    message: ChatMessage


class ChoiceStreaming(ChoiceBase):
    delta: ChatDelta


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{secrets.token_hex(12)}")
    object: Literal["chat.completion", "chat.completion.chunk"]
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[Union[ChoiceNonStreaming, ChoiceStreaming]]
    usage: Optional[Any] = None

    def to_json(self) -> str:
        """The Sovereign Serializer: Fast, Rust-based, Excludes None"""
        return self.model_dump_json(exclude_none=True)


def str_to_streaming(json_str: str) -> str:
    return f"data: {json_str}\n\n"


class ChatTemplatesKwargs(BaseModel):
    add_generation_prompt: bool = True
    use_default_system_prompt: bool = True


class ChatPost(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    model: str
    messages: List[ChatMessage]
    stream: bool = False

    api_base: Optional[str] = Field(
        default=None,
        description="Base URL of the model endpoint; overrides the provider default resolved from `model`.",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key used to authenticate against the endpoint.",
    )

    modalities: List[Literal["text", "audio"]] = Field(default=["text"])
    audio: Optional[Any] = None

    tools: Optional[List[ChatTool]] = None
    tool_choice: Optional[Union[Literal["auto", "none", "required"], Dict[str, Any]]] = None

    response_format: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Enforce JSON schema: {'type': 'json_object'}"
    )

    max_tokens: Optional[int] = Field(default=None, alias="max_completion_tokens")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=0)
    min_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    repetition_penalty: Optional[float] = None
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)

    stop: Optional[Union[str, List[str]]] = None

    chat_template_kwargs: Optional[ChatTemplatesKwargs] = Field(default_factory=ChatTemplatesKwargs)
    seed: Optional[int] = None
