import asyncio
import random
from typing import List, Type, TypeVar, Tuple, Optional

import litellm

from litellm import ModelResponse
from litellm.types.utils import Choices, Usage
from pydantic import BaseModel

from chat.parse_model_output import get_schema, parse_model_output_json
from chat.tools.abstract import Tool
from chat.tools.context import ToolContext
from chat.tools.tools import execute_tools
from chat.types import ChatPost, ChatMessage, ChatMessageAssistant, ToolCall


T = TypeVar("T", bound=BaseModel)


class ChatUsage(BaseModel):
    model: str

    completion_tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0

    reasoning_tokens: int | None = None

    cost: float | None = None
    prompt_cost: float | None = None
    completion_cost: float | None = None

    def consume_usage(self, usage: "ChatUsage", clear_model: bool = False):
        if clear_model:
            self.model = ""
            usage.model = ""

        if usage.model != self.model:
            raise Exception(f"Failed to consume_usage: {self.model} != {usage.model}")

        self.completion_tokens += usage.completion_tokens
        self.prompt_tokens += usage.prompt_tokens
        self.total_tokens += usage.total_tokens

        for field in ("reasoning_tokens", "cost", "prompt_cost", "completion_cost"):
            value = getattr(usage, field)
            if value is not None:
                setattr(self, field, (getattr(self, field) or 0) + value)


async def chat_completion_not_stream(
        post: ChatPost,
) -> Tuple[ModelResponse, ChatUsage]:
    payload = post.model_dump(exclude_none=True, exclude={"messages", "model", "stream"})

    if post.model_extra:
        payload.update(post.model_extra)

    response = await litellm.acompletion(
        model=post.model,
        messages=[m.model_dump(exclude_none=True) for m in post.messages],
        stream=False,
        **payload
    )
    assert isinstance(response, ModelResponse)
    usage: Usage = getattr(response, "usage")

    if usage.completion_tokens_details and getattr(usage.completion_tokens_details, "reasoning_tokens"):
        reasoning_tokens = usage.completion_tokens_details.reasoning_tokens
    else:
        reasoning_tokens = None

    cost_details = getattr(usage, "cost_details") or {}

    chat_usage = ChatUsage(
        model=post.model,
        completion_tokens=usage.completion_tokens,
        prompt_tokens=usage.prompt_tokens,
        total_tokens=usage.total_tokens,
        reasoning_tokens=reasoning_tokens,

        cost=usage.cost,
        prompt_cost=cost_details.get("upstream_inference_prompt_cost"),
        completion_cost=cost_details.get("upstream_inference_completions_cost"),
    )

    return response, chat_usage


async def chat_completion_not_stream_with_tools(
        ctx: ToolContext,
        post: ChatPost,
        tools: List[Tool],
        response_model: Optional[Type[T]] = None,
        max_depth: int = 10,
) -> Tuple[ModelResponse | T | None, ChatUsage, List[ChatMessage]]:
    usage_acc = ChatUsage(model=post.model)
    post_copy = post.model_copy()
    messages = post.messages
    structured_response: Optional[T] = None

    depth = 0
    while True:
        depth += 1
        if depth >= max_depth and post_copy.tools is not None:
            post_copy.tools.clear()

        post_copy.messages = messages

        if response_model:
            structured_response, raw_response, usage = await chat_completion_not_stream_structured(post_copy, response_model)
        else:
            raw_response, usage = await chat_completion_not_stream(post_copy)

        usage_acc.consume_usage(usage)

        choices = [c for c in raw_response.choices if isinstance(c, Choices)]
        message = choices[0].message

        tool_calls = [
            ToolCall.model_validate(t.model_dump())
            for t in message.tool_calls or []
        ]

        if tool_calls:
            response_msg = ChatMessageAssistant(
                content=message.content,
                tool_calls=tool_calls,
            )
            messages.append(response_msg)
            messages.extend(await execute_tools(ctx, tools, messages))
            continue

        if structured_response is not None:
            return structured_response, usage_acc, messages

        return raw_response, usage_acc, messages

    raise RuntimeError("unreachable")


async def chat_completion_not_stream_structured(
        post: ChatPost,
        response_model: Type[T],

        max_retries: int = 2,
        backoff_base: float = 1.5,
) -> Tuple[Optional[T], ModelResponse, ChatUsage]:
    usage_acc = ChatUsage(model=post.model)

    post_copy = post.model_copy()
    post_copy.response_format = get_schema(response_model)

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            raw_response, usage = await chat_completion_not_stream(post=post_copy)
            usage_acc.consume_usage(usage)

            choices = [c for c in raw_response.choices if isinstance(c, Choices)]
            content = choices[0].message.content
            structured_response = parse_model_output_json(content, response_model) if content else None

            return structured_response, raw_response, usage_acc

        except Exception as e:
            last_error = e
            if attempt == max_retries:
                break
            delay = (backoff_base ** attempt) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error
