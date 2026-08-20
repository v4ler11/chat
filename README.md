## chat

Typed LLM chat client library with tool-calling and structured-output support, built on [litellm](https://github.com/BerriAI/litellm).

## Install

```sh
uv add ssh://git@ssh.git.valerii.casa/valerii/chat.git
```

## Usage

`ChatPost` carries the request. The model endpoint is resolved by litellm from the `model` string (e.g. `"gpt-4o"` → OpenAI, `"ollama/llama3"` → local Ollama); to point at a custom or self-hosted endpoint, pass `api_base` (and `api_key` if the endpoint requires it) — both are forwarded straight to litellm:

```python
import asyncio

from chat import ChatPost, ChatMessageUser, chat_completion_not_stream


async def main():
    post = ChatPost(
        model="openai/model-name",          # litellm provider prefix
        messages=[ChatMessageUser(content="Hello")],
        api_base="http://localhost:95255/v1",  # endpoint override
        api_key="sk-...",                      # auth for that endpoint
    )
    response, usage = await chat_completion_not_stream(post)
    print(response.choices[0].message.content)
    print(usage.model_dump())


asyncio.run(main())
```

Any other litellm `acompletion` kwarg can be passed as an extra field (`ChatPost` allows extras) and is forwarded as-is.

### Structured output

Enforce a Pydantic response schema (with retries):

```python
from pydantic import BaseModel

from chat import ChatPost, ChatMessageUser, chat_completion_not_stream_structured


class Response(BaseModel):
    answer: str


async def main():
    post = ChatPost(
        model="gpt-4o",
        messages=[ChatMessageUser(content="What is 2+2?")],
    )
    parsed, response, usage = await chat_completion_not_stream_structured(post, Response)
    print(parsed.answer)
```

### Tool calling

Subclass `Tool` and pass your own list of instances:

```python
import aiohttp

from chat import (
    ChatPost,
    ChatMessageUser,
    Tool,
    ToolCall,
    ToolContext,
    ToolProps,
    chat_completion_not_stream_with_tools,
)


class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    def props(self) -> ToolProps:
        return ToolProps(tool_name=self.name)

    def into_chat_tool(self):
        return ...  # ChatTool description/schema

    def validate_tool_call_args(self, ctx, tool_call, args):
        return True, []

    async def execute(self, ctx, tool_call, args):
        return True, []  # ChatMessageTool results


TOOLS = [EchoTool()]


async def main():
    async with aiohttp.ClientSession() as session:
        ctx = ToolContext(session=session)
        post = ChatPost(
            model="gpt-4o",
            messages=[ChatMessageUser(content="Please echo!")],
            tools=[t.into_chat_tool() for t in TOOLS],
            tool_choice="auto",
        )
        response, usage, history = await chat_completion_not_stream_with_tools(
            ctx, post, TOOLS, max_depth=10,
        )
        print(response.choices[0].message.content)
        # `history` is the full message list: user + assistant tool calls + tool results
        assert history[-1].content == response.choices[0].message.content
```

## Development

```sh
uv sync --dev
uv run pyright
uv run pytest
```