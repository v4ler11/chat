import asyncio
import inspect
from typing import AsyncIterator, List, Callable, Awaitable, Any
from collections.abc import AsyncIterator as AsyncIteratorAbc

from mcp.lifecycle_manager import LifecycleManager
from mcp.schemas.other import (
    JsonRpcRequest, JsonRpcResponse, JsonRpcError, METHOD_NOT_FOUND, INTERNAL_ERROR,
    JsonRpcResponseInitializeResult, INVALID_PARAMS,
    RESOURCE_NOT_FOUND
)
from mcp.schemas.progress import ProgressNotification, ProgressNotificationParams
from mcp.schemas.prompts import PromptsResponse, PromptsListResponseResult, PromptsChangedResponse, Prompt
from mcp.schemas.resources import (
    ResourcesResponse, ResourcesListResponseResult,
    ResourcesReadResponseResult, ResourcesTemplatesListResult,
    ResourcesChangedNotification, Resource, ResourceTemplate
)
from mcp.schemas.tools import (
    MCPToolResultText, MCPToolsResponse, MCPToolsCallResult, MCPToolsListResponseResult,
    MCPToolsChangedNotification, MCPToolProgress, MCPToolResult, MCPTool
)


class MCPServer:
    VERSION = "1.0.0"

    def __init__(self, name: str):
        self.name = name

        self._notification_handlers: List[Callable[[dict], Awaitable[None]]] = []

        self.tools: LifecycleManager[MCPTool] = LifecycleManager(
            on_change=self._on_tools_changed,
            id_getter=lambda t: t.definition.name
        )
        self.prompts: LifecycleManager[Prompt] = LifecycleManager(
            on_change=self._on_prompts_changed,
            id_getter=lambda p: p.definition.name
        )
        self.resources: LifecycleManager[Resource] = LifecycleManager(
            on_change=self._on_resources_changed,
            id_getter=lambda r: r.data.uri
        )
        self.resources_templates: LifecycleManager[ResourceTemplate] = LifecycleManager(
            on_change=self._on_resources_templates_changed,
            id_getter=lambda r: r.name
        )

        # todo: set log level
        # todo: handle pagination?

    def subscribe(self, handler: Callable[[dict], Awaitable[None]]):
        self._notification_handlers.append(handler)

    async def notify_clients(self, event: Any):
        await asyncio.gather(
            *(
                handler(event)
                for handler in self._notification_handlers
            ),
            return_exceptions=True
        )

    def _schedule_notify(self, event: Any):
        # Tools/prompts/resources may be registered before the event loop is
        # running. Only broadcast when there is a live loop; otherwise there
        # are no clients to notify yet.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        asyncio.create_task(self.notify_clients(event))

    def _on_tools_changed(self):
        self._schedule_notify(MCPToolsChangedNotification())

    def _on_prompts_changed(self):
        self._schedule_notify(PromptsChangedResponse())

    def _on_resources_changed(self):
        self._schedule_notify(ResourcesChangedNotification())

    def _on_resources_templates_changed(self):
        pass

    async def process_request(
            self, request: JsonRpcRequest
    ) -> AsyncIterator[
        JsonRpcResponse | JsonRpcError | None |
        ProgressNotification | MCPToolsResponse |
        PromptsResponse | ResourcesResponse
    ]:
        try:
            if request.method == "initialize":
                yield self._handle_initialize(request)

            elif request.method == "notifications/initialized":
                yield None

            elif request.method == "ping":
                yield JsonRpcResponse(id=request.id, result={})

            elif request.method == "tools/list":
                yield self._handle_tools_list(request)

            elif request.method == "tools/call":
                async for response in self._handle_tool_call(request):
                    yield response

            elif request.method == "prompts/list":
                yield self._handle_prompts_list(request)

            elif request.method == "prompts/get":
                yield await self._handle_prompts_get(request)

            elif request.method == "resources/list":
                yield self._handle_resources_list(request)

            elif request.method == "resources/read":
                yield self._handle_resources_read(request)

            elif request.method == "resources/templates/list":
                yield self._handle_resources_templates_list(request)

            else:
                yield JsonRpcError(
                    id=request.id,
                    code=METHOD_NOT_FOUND,
                    message=f"Method '{request.method}' not supported"
                )

        except Exception as e:
            yield JsonRpcError(
                id=request.id,
                code=INTERNAL_ERROR,
                message=f"Internal Server Error: {str(e)}"
            )

    def _handle_initialize(self, request: JsonRpcRequest) -> JsonRpcResponse:
        return JsonRpcResponse(
            id=request.id,
            result=JsonRpcResponseInitializeResult.new(self.name, self.VERSION)
        )


    def _handle_resources_list(self, request: JsonRpcRequest) -> ResourcesResponse:
        return ResourcesResponse(
            id=request.id,
            result=ResourcesListResponseResult(
                resources=[r.definition for r in self.resources.list()]
            )
        )

    def _handle_resources_read(self, request: JsonRpcRequest) -> ResourcesResponse | JsonRpcError:
        params = request.params
        if not isinstance(params, dict):
            return JsonRpcError(id=request.id, code=INVALID_PARAMS, message="Params must be a dictionary")

        uri = params.get("uri")
        if not uri:
            return JsonRpcError(id=request.id, code=INVALID_PARAMS, message="Missing 'uri' in parameters")

        resource = self.resources.get(uri)

        if resource is None:
            return JsonRpcError(
                id=request.id,
                code=RESOURCE_NOT_FOUND,
                message="Resource not found",
                data=dict(
                    uri=uri
                )
            )

        return ResourcesResponse(
            id=request.id,
            result=ResourcesReadResponseResult(
                contents=[resource.data],
            )
        )

    def _handle_resources_templates_list(self, request: JsonRpcRequest) -> ResourcesResponse:
        return ResourcesResponse(
            id=request.id,
            result=ResourcesTemplatesListResult(
                resourceTemplates=self.resources_templates.list()
            )
        )

    def _handle_prompts_list(self, request: JsonRpcRequest) -> PromptsResponse:
        return PromptsResponse(
            id=request.id,
            result=PromptsListResponseResult(
                prompts=[p.definition for p in self.prompts.list()]
            )
        )

    async def _handle_prompts_get(
            self, request: JsonRpcRequest
    ) -> PromptsResponse | JsonRpcError:
        params = request.params
        if not isinstance(params, dict):
            return JsonRpcError(id=request.id, code=INVALID_PARAMS, message="Params must be a dictionary")

        prompt_name = params.get("name")
        prompt_arguments = params.get("arguments", {})

        if not prompt_name:
            return JsonRpcError(id=request.id, code=INVALID_PARAMS, message="Missing 'name' in parameters")

        prompt = self.prompts.get(prompt_name)

        if prompt is None:
            return JsonRpcError(id=request.id, code=INVALID_PARAMS, message=f"Prompt '{prompt_name}' not found")
        try:
            prompt_result = await asyncio.wait_for(
                prompt.func(prompt_arguments),
                timeout=prompt.timeout
            )
        except asyncio.TimeoutError:
            return JsonRpcError(id=request.id, code=INTERNAL_ERROR, message=f"Prompt '{prompt_name}' timed out (> {prompt.timeout}s).")

        return PromptsResponse(
            id=request.id,
            result=prompt_result
        )

    def _handle_tools_list(self, request: JsonRpcRequest) -> MCPToolsResponse:
        return MCPToolsResponse(
            id=request.id,
            result=MCPToolsListResponseResult(
                tools=[t.definition for t in self.tools.list()]
            )
        )

    async def _handle_tool_call(
            self, request: JsonRpcRequest
    ) -> AsyncIterator[ProgressNotification | MCPToolsResponse | JsonRpcError]:

        params = request.params
        if not isinstance(params, dict):
            yield JsonRpcError(id=request.id, code=INVALID_PARAMS, message="Params must be a dictionary")
            return

        tool_name = params.get("name")
        args = params.get("arguments", {})
        progress_token = params.get("progressToken") or params.get("_meta", {}).get("progressToken")

        if not tool_name:
            yield JsonRpcError(id=request.id, code=INVALID_PARAMS, message="Missing 'name'")
            return

        tool = self.tools.get(tool_name)
        if tool is None:
            yield MCPToolsResponse(
                id=request.id,
                result=MCPToolsCallResult(
                    content=[MCPToolResultText(text=f"Tool '{tool_name}' not found.")],
                    isError=True,
                )
            )
            return


        deadline = asyncio.get_running_loop().time() + tool.timeout

        try:
            raw_result = tool.func(args)

            iterator: AsyncIterator[MCPToolProgress | MCPToolResult]

            if isinstance(raw_result, AsyncIteratorAbc):
                iterator = raw_result
            elif inspect.isawaitable(raw_result):
                async def _wrapper():
                    yield await raw_result

                iterator = _wrapper()
            else:
                yield MCPToolsResponse(
                    id=request.id,
                    result=MCPToolsCallResult(
                        content=[MCPToolResultText(text=f"Invalid tool return type: {type(raw_result)}")],
                        isError=True,
                    )
                )
                return

            result_sent = False

            while True:
                time_remaining = deadline - asyncio.get_running_loop().time()
                if time_remaining <= 0:
                    raise asyncio.TimeoutError()

                try:
                    tool_output = await asyncio.wait_for(
                        iterator.__anext__(),
                        timeout=time_remaining
                    )

                    if isinstance(tool_output, MCPToolProgress):
                        if progress_token is not None:
                            yield ProgressNotification(
                                params=ProgressNotificationParams(
                                    progressToken=progress_token,
                                    progress=tool_output.progress,
                                    total=tool_output.total,
                                    message=tool_output.message
                                )
                            )

                    elif isinstance(tool_output, MCPToolResult):
                        result_sent = True
                        yield MCPToolsResponse(
                            id=request.id,
                            result=MCPToolsCallResult(
                                content=tool_output.content,
                                structuredContent=tool_output.structuredContent,
                                isError=tool_output.isError
                            )
                        )
                        break

                    else:
                        pass

                except StopAsyncIteration:
                    break

            if not result_sent:
                yield MCPToolsResponse(
                    id=request.id,
                    result=MCPToolsCallResult(
                        content=[MCPToolResultText(text=f"Tool '{tool_name}' finished without returning a result.")],
                        isError=True
                    )
                )

        except asyncio.TimeoutError:
            yield MCPToolsResponse(
                id=request.id,
                result=MCPToolsCallResult(
                    content=[MCPToolResultText(text=f"Tool execution timed out ({tool.timeout}s).")],
                    isError=True
                )
            )
        except Exception as e:
            yield MCPToolsResponse(
                id=request.id,
                result=MCPToolsCallResult(
                    content=[MCPToolResultText(text=f"Internal Tool Error: {str(e)}")],
                    isError=True
                )
            )
