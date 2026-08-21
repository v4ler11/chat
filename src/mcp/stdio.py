import asyncio
import json
import sys
from typing import Any, IO

from asyncio import protocols
from asyncio.streams import FlowControlMixin
from pydantic import ValidationError

from mcp.server import MCPServer
from mcp.schemas.other import (
    JsonRpcRequest, JsonRpcResponse, JsonRpcError,
    PARSE_ERROR, INVALID_REQUEST, INTERNAL_ERROR,
)


class _StreamWriterProtocol(FlowControlMixin, protocols.Protocol):
    """Minimal write-protocol for asyncio.StreamWriter.

    ``asyncio.StreamWriterProtocol`` was removed from the stdlib in Python
    3.12; this is its pre-3.12 implementation (FlowControlMixin plus a close
    waiter), which is what the reference MCP SDK's fallback relied on.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        super().__init__(loop=loop)
        self._transport: asyncio.BaseTransport | None = None
        self._close_waiter: asyncio.Future[None] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport

    def connection_lost(self, exc: Exception | None) -> None:
        super().connection_lost(exc)

        waiter = self._close_waiter
        if waiter is not None:
            self._close_waiter = None
            if not waiter.cancelled():
                if exc is None:
                    waiter.set_result(None)
                else:
                    waiter.set_exception(exc)

    def _get_close_waiter(self, stream: asyncio.StreamWriter):
        if self._close_waiter is None:
            self._close_waiter = asyncio.get_running_loop().create_future()
        return self._close_waiter


class StdioServer:
    """Runs an :class:`MCPServer` over newline-delimited JSON-RPC on stdin/stdout.

    Per the MCP 2025-11-25 transports spec, the stdio transport exchanges one
    JSON-RPC message per line. Messages are processed sequentially: each
    request's full response stream is drained before the next input line is
    read, matching the single-request-at-a-time behavior of MCP stdio clients.
    """

    def __init__(
        self,
        server: MCPServer,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ):
        self.server = server
        self._stdin = stdin
        self._stdout = stdout
        self._writer: asyncio.StreamWriter | None = None

    async def _write(self, msg: Any, writer: asyncio.StreamWriter) -> None:
        """Serialize a message and write it as a single newline-delimited line."""
        payload = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        writer.write(payload)
        await writer.drain()

    async def _write_error(
        self,
        code: int,
        message: str,
        writer: asyncio.StreamWriter,
        request_id: str | int | None = None,
    ) -> None:
        await self._write(
            JsonRpcError(code=code, message=message, id=request_id).model_dump(),
            writer,
        )

    async def _on_server_event(self, event: Any) -> None:
        """Broadcast a server-initiated notification (e.g. tools/list_changed).

        Serializes the Pydantic model first; stdlib ``json.dumps`` raises
        ``TypeError`` on a bare ``BaseModel``.
        """
        writer = self._writer
        if writer is not None:
            await self._write(event.model_dump(exclude_none=True), writer)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        stdin = self._stdin or sys.stdin
        stdout = self._stdout or sys.stdout

        # Read side: a worker-thread blocking readline instead of
        # connect_read_pipe. Files and /dev/null are not pollable on macOS
        # kqueue (registering the fd for reading raises EINVAL), which would
        # hang connect_read_pipe on stdin EOF. Blocking readline handles
        # pipes, PTYs, files, and /dev/null identically, returning b'' at EOF.
        read_stream = getattr(stdin, "buffer", stdin)

        write_transport, write_protocol = await loop.connect_write_pipe(
            lambda: _StreamWriterProtocol(loop=loop), stdout
        )
        writer = asyncio.StreamWriter(write_transport, write_protocol, None, loop)
        self._writer = writer

        self.server.subscribe(self._on_server_event)

        try:
            while True:
                raw_line = await asyncio.to_thread(read_stream.readline)
                if not raw_line:
                    # stdin EOF ends the session.
                    break

                if isinstance(raw_line, bytes):
                    try:
                        raw_line = raw_line.decode("utf-8")
                    except UnicodeDecodeError as e:
                        await self._write_error(
                            PARSE_ERROR, f"cannot decode request: {e}", writer
                        )
                        continue

                line = raw_line.strip()
                if not line:
                    # Tolerate trailing newlines / blank lines; no response.
                    continue

                try:
                    body = json.loads(line)
                except (json.JSONDecodeError, ValueError) as e:
                    await self._write_error(PARSE_ERROR, f"cannot parse request: {e}", writer)
                    continue

                if isinstance(body, list):
                    await self._write_error(INVALID_REQUEST, "batching is not supported", writer)
                    continue

                if not isinstance(body, dict):
                    await self._write_error(INVALID_REQUEST, "request must be a JSON object", writer)
                    continue

                try:
                    rpc_req = JsonRpcRequest(**body)
                except ValidationError as e:
                    await self._write_error(
                        INVALID_REQUEST, str(e), writer, request_id=body.get("id")
                    )
                    continue

                try:
                    async for result in self.server.process_request(rpc_req):
                        if result is None:
                            continue
                        # JSON-RPC: a notification must not receive a response.
                        if rpc_req.id is None and isinstance(result, (JsonRpcResponse, JsonRpcError)):
                            continue
                        await self._write(result.model_dump(exclude_none=True), writer)
                except Exception as e:
                    await self._write(
                        JsonRpcError(
                            code=INTERNAL_ERROR,
                            id=rpc_req.id,
                            message=f"Internal processing error: {e}",
                        ).model_dump(),
                        writer,
                    )
        finally:
            writer.close()
            await writer.wait_closed()


def run_stdio(server: MCPServer) -> None:
    """Run ``server`` as a spec-compliant stdio MCP server (blocking call)."""
    asyncio.run(StdioServer(server).run())
