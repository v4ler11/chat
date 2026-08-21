## chat

Typed LLM chat client library with tool-calling and structured-output support, built on [litellm](https://github.com/BerriAI/litellm).

## Install

```sh
uv add git+ssh://git@ssh.git.valerii.casa/valerii/chat.git
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
    ToolContext,
    chat_completion_not_stream_with_tools,
)


class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

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

## sovereign-mcp

**sovereign-mcp** is a strict, framework-free implementation of the Model Context Protocol (MCP) server specification (Version `2025-11-25`).

It exists because the reference Python implementation (`FastMCP`) relies on opaque "magic" decorators and implicit global state. **sovereign-mcp** is architected for transparency and total control. It enforces strict separation of concerns, explicit state management, and direct transport adherence.

Instead of vague dictionaries, it utilizes **Pydantic** for rigid schema validation and type safety, ensuring every protocol message is formally verified before transmission.

### Core Philosophy

* **No Magic:** Rejection of implicit global state. Everything is explicitly instantiated and injected.
* **Transport Agnostic:** Logic is decoupled from the HTTP layer.
* **Deterministic Lifecycle:** Tools and Prompts are managed via strict `LifecycleManager` instances.
* **Type Safety:** Heavy use of Pydantic models for request/response validation, eliminating "stringly typed" errors.

### Technical Specifications

* **Protocol:** `2025-11-25`
* **Transport:** StreamableHTTP (Server-Sent Events for downstream updates + JSON-RPC 2.0 via HTTP POST for upstream commands); **Stdio** (newline-delimited JSON-RPC over stdin/stdout).
* **Concurrency:** Built on the native `asyncio` event loop. Fully non-blocking I/O with support for both atomic `awaitable` coroutines and `AsyncIterator` generators for real-time progress streaming.

### Constraints

* **Authentication:** Not implemented. Security and auth headers are delegated to the host application (FastAPI) or infrastructure layer (e.g., Nginx, API Gateway).
* **JSON-RPC Batching:** Unsupported. All requests must be sent sequentially.
* **Stdio:** messages processed sequentially — one request fully answered before the next stdin line is read.

### Usage

sovereign-mcp is a library (Dev Kit), not a standalone application. It supports two transports: **StreamableHTTP**, mounted within a FastAPI host, and **Stdio**, run via `run_stdio` in your own entry script.

**1. Install using uv**

```sh
uv add git+https://github.com/v4ler11/sovereign-mcp.git
```

**2. Define Capabilities**

Capabilities are defined as standalone objects. Logic is isolated from definition.

```python
import asyncio
from typing import AsyncIterator, Dict, Any
from mcp.schemas.tools import MCPTool, MCPToolResult, MCPToolResultText, MCPToolDefinition, MCPToolProgress
from mcp.schemas.prompts import Prompt, PromptDefinition, PromptsGetResult, PromptMessage, PromptMessageContentText, PromptArgument


# --- Tool: Standard (Sync/Async) ---
async def calculate_sum(args: dict) -> MCPToolResult:
    result = args['a'] + args['b']
    return MCPToolResult(content=[MCPToolResultText(text=str(result))])

tool_calc = MCPTool(
    func=calculate_sum,
    definition=MCPToolDefinition(
        name="add",
        description="Adds two integers.",
        inputSchema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"]
        }
    )
)

# --- Tool: Streaming (Progress) ---
async def long_process(args: dict) -> AsyncIterator[MCPToolResult | MCPToolProgress]:
    for i in range(5):
        yield MCPToolProgress(progress=i, total=5, message="Processing...")
        await asyncio.sleep(0.1)

    yield MCPToolResult(content=[MCPToolResultText(text="Done")])

tool_stream = MCPTool(
    func=long_process,
    definition=MCPToolDefinition(
        name="process_stream",
        description="Demonstrates progress reporting.",
        inputSchema={"type": "object", "properties": {}, "required": []}
    )
)

# --- Prompt ---
async def make_system_prompt(args: Dict[str, Any]) -> PromptsGetResult:
    return PromptsGetResult(
        description="System Instructions",
        messages=[
            PromptMessage(
                role="user",
                content=PromptMessageContentText(text=f"Act as a {args.get('role', 'assistant')}.")
            )
        ]
    )

prompt_sys = Prompt(
    func=make_system_prompt,
    definition=PromptDefinition(
        name="system_persona",
        description="Generates dynamic system prompts.",
        arguments=[PromptArgument(name="role", required=False)]
    )
)
```

**3. Server Instantiation**

Compose the server by injecting capabilities

```python
from mcp.server import MCPServer

def create_server() -> MCPServer:
    server = MCPServer("node-01")

    # Explicit registration
    server.tools.add([tool_calc, tool_stream])
    server.prompts.add([prompt_sys])

    return server
```

**4. Entry Point (FastAPI)**

Mount the MCPRouter.

```python
from fastapi import FastAPI
from mcp.router import MCPRouter

app = FastAPI()
server = create_server()

app.include_router(MCPRouter(server=server))
```

**5. Entry Point (Stdio)**

Run the server over stdin/stdout so an MCP client can spawn it directly with a `command` + `args` + `env` in its config — no HTTP host required.

```python
from mcp.server import MCPServer
from mcp.stdio import run_stdio

def create_server() -> MCPServer:
    # ... register tools/prompts/resources as above ...
    return server

if __name__ == "__main__":
    run_stdio(create_server())
```

Example:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'   \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}'        \
  '{"jsonrpc":"2.0","id":2,"method":"ping"}'                      \
  '{"jsonrpc":"2.0","id":3,"method":"tools/list"}'                \
  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"add","arguments":{"a":2,"b":3}}}' \
| $PY $SRV 2>/dev/null | python3 -m json.tool --json-lines
```

```sh
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "protocolVersion": "2025-11-25",
        "capabilities": {
            "prompts": {
                "listChanged": true
            },
            "resources": {
                "subscribe": true,
                "listChanged": true
            },
            "tools": {
                "listChanged": true
            }
        },
        "serverInfo": {
            "name": "stdio-demo",
            "version": "1.0.0"
        }
    }
}
{
    "jsonrpc": "2.0",
    "id": 2,
    "result": {}
}
{
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
        "tools": [
            {
                "name": "add",
                "description": "Adds two integers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "integer"
                        },
                        "b": {
                            "type": "integer"
                        }
                    },
                    "required": [
                        "a",
                        "b"
                    ]
                }
            },
            {
                "name": "process_stream",
                "description": "Demonstrates progress reporting.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    }
}
{
    "jsonrpc": "2.0",
    "id": 4,
    "result": {
        "content": [
            {
                "type": "text",
                "text": "5"
            }
        ],
        "isError": false
    }
}
```

Point an MCP client at your entry script. "Tool execution options" (argv and environment) are supplied by the client to the spawned process:

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["/absolute/path/to/your/stdio_server.py"],
      "env": { "API_KEY": "..." }
    }
  }
}
```

Add to your project
```sh
uv add git+ssh://git@ssh.git.valerii.casa/valerii/sovereign-mcp.git
```

Notes on the stdio transport:

* **stdout** carries only JSON-RPC messages — one per line, newline-delimited. Never `print()` to stdout.
* Logs go to **stderr**.
* argv and env are provided by the client to the spawned process; there is no server-side tool filtering.
* The server exits cleanly when the client closes stdin.
* The Stdio entry point above is a working starting point: run it and connect a client to demonstrate progress streaming.

### Protocol Compliance

| Feature             | Status | Notes                                                                        |
|:--------------------|:------:|:-----------------------------------------------------------------------------|
| **JSON-RPC 2.0**    |   ✓    | Pydantic validation.                                                         |
| **StreamableHTTP**  |   ✓    | Single endpoint. POST sends (accepts SSE/JSON)                               |
| **Stdio**           |   ✓    | Newline-delimited JSON-RPC over stdin/stdout, one message per line.          |
| **Tools**           |   ✓    | Async support.                                                               |
| **Prompts**         |   ✓    | Dynamic generation.                                                          |
| **Resources**       |   ✓    | URI context. No pagination.                                                  |
| **ResourceSchemas** |   ✓    | RFC 6570 templates.                                                          |
| **Progress**        |   ✓    | Tool-driven reporting.                                                       |
| **Batching**        |   X    | Unsupported.                                                                 |
| **Auth**            |   X    | Host-delegated.                                                              |

### License

MIT

## Development

```sh
uv sync --dev
uv run pyright
uv run pytest
```