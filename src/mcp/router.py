import asyncio
import json
import uuid
import time

from typing import Dict, Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse

from mcp.schemas.other import JsonRpcError, PARSE_ERROR, INVALID_REQUEST, JsonRpcRequest, INTERNAL_ERROR
from mcp.server import MCPServer
from mcp.session import Session


class MCPRouter(APIRouter):
    HEADER_SESSION_ID_KEY: str = "Mcp-Session-Id"
    CLEANUP_INTERVAL: int = 300
    SESSION_TIMEOUT: int = 86400

    def __init__(self, server: MCPServer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server = server
        self.sessions: Dict[str, Session] = {}

        self.server.subscribe(self._broadcast_event)
        self._cleanup_task = asyncio.create_task(self._monitor_sessions())

        self.add_api_route("/mcp", self.handle_mcp, methods=["POST", "GET", "DELETE"])

    async def _broadcast_event(self, notification: Any):
        if not self.sessions:
            return

        for session in self.sessions.values():
            if session.active:
                session.enqueue_message(notification)

    async def handle_mcp(self, request: Request):
        if request.method == "GET":
            return await self._handle_get(request)

        elif request.method == "POST":
            return await self._handle_post(request)

        elif request.method == "DELETE":
            return await self._handle_delete(request)

        return Response(status_code=405)

    async def _handle_get(self, request: Request) -> Response:
        session_id = request.headers.get(self.HEADER_SESSION_ID_KEY) or str(uuid.uuid4())

        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id)

        session = self.sessions[session_id]
        session.touch()

        return StreamingResponse(
            self.sse_generator(session),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                self.HEADER_SESSION_ID_KEY: session.id
            }
        )

    async def _handle_post(self, request: Request) -> Response:
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return Response(status_code=415, content="content-type must be application/json")

        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content=JsonRpcError(
                    code=PARSE_ERROR, message=f"cannot parse request body: {str(e)}"
                ).model_dump()
            )

        if isinstance(body, list):
            # todo: support batching
            return JSONResponse(
                status_code=400,
                content=JsonRpcError(
                    code=INVALID_REQUEST, message="batching is not supported"
                ).model_dump()
            )

        rpc_req = JsonRpcRequest(**body)
        session_id = request.headers.get(self.HEADER_SESSION_ID_KEY)

        if rpc_req.method == "initialize":
            return await self._create_session(rpc_req, session_id)

        if not session_id:
            return Response(status_code=400, content=f"{self.HEADER_SESSION_ID_KEY} is missing")

        session: Session | None = self.sessions.get(session_id)
        if not session:
            return Response(status_code=404, content=f"session {session_id} is not found")

        session.touch()
        asyncio.create_task(self._process_background(session, rpc_req))

        return Response(status_code=202)

    async def _process_background(self, session: Session, rpc_req: JsonRpcRequest):
        try:
            async for result in self.server.process_request(rpc_req):
                if result:
                    session.enqueue_message(result.model_dump(exclude_none=True))

        except Exception as e:
            err_resp = JsonRpcError(
                id=rpc_req.id,
                code=INTERNAL_ERROR,
                message=f"Internal processing error: {str(e)}"
            )
            session.enqueue_message(err_resp.model_dump())

    async def _create_session(self, rpc_req: JsonRpcRequest, existing_session_id: str | None = None) -> Response:
        new_sess_id = existing_session_id or str(uuid.uuid4())

        if new_sess_id not in self.sessions:
            session = Session(new_sess_id)
            self.sessions[new_sess_id] = session

        rpc_resp = None
        async for res in self.server.process_request(rpc_req):
            rpc_resp = res
            break

        if not rpc_resp:
            return Response(status_code=500, content="Initialization failed to produce response")

        return JSONResponse(
            content=rpc_resp.model_dump(exclude_none=True),
            headers={self.HEADER_SESSION_ID_KEY: new_sess_id}
        )

    async def _handle_delete(self, request: Request) -> Response:
        session_id = request.headers.get(self.HEADER_SESSION_ID_KEY)
        if not session_id:
            return Response(status_code=400)

        session = self.sessions.pop(session_id, None)
        if session:
            session.terminate()
            return Response(status_code=200)

        return Response(status_code=404)

    @staticmethod
    async def sse_generator(session: Session):
        try:
            yield ": connected\n\n"

            while session.active:
                try:
                    msg = await asyncio.wait_for(session.msg_queue.get(), timeout=60.0)

                    event_id = str(int(time.time() * 1000))
                    payload = json.dumps(msg)

                    yield f"id: {event_id}\nevent: message\ndata: {payload}\n\n"

                    session.touch()

                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    session.touch()

        except asyncio.CancelledError:
            pass

        except Exception as e:
            pass

    def __del__(self):
        if hasattr(self, '_cleanup_task'):
            self._cleanup_task.cancel()

    async def _monitor_sessions(self):
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                cutoff = time.time() - self.SESSION_TIMEOUT

                for session_id in list(self.sessions.keys()):
                    session = self.sessions[session_id]
                    if session.last_accessed < cutoff:
                        session.terminate()
                        self.sessions.pop(session_id, None)

            except asyncio.CancelledError:
                break

            except Exception as e:
                pass
