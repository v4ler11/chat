import json

from typing import List

from chat.tools.abstract import Tool
from chat.tools.context import ToolContext
from chat.types import ChatMessage, ChatMessageTool
from chat.utils import messages_since_last_user_message, get_unanswered_tool_calls


async def execute_tools(
        ctx: ToolContext,
        tools: List[Tool],
        messages: List[ChatMessage],
) -> List[ChatMessageTool]:
    messages = messages_since_last_user_message(messages)

    tool_res_messages = []
    for tool_call in get_unanswered_tool_calls(messages):
        tool = next((t for t in tools if t.name == tool_call.function.name), None)
        if not tool:
            # The model asked for a tool that is not declared to us. Every
            # unanswered assistant tool call must still get a tool/reply, or the
            # transcript ends on a model turn and Gemini (Google AI Studio)
            # rejects the next request ("Requests ending with a model turn are
            # not supported"). Reply so the model can recover.
            tool_res_messages.append(ChatMessageTool(
                content=f"Unknown tool '{tool_call.function.name}': no such tool is available in this session.",
                tool_call_id=tool_call.id,
            ))
            continue

        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            tool_res_messages.append(ChatMessageTool(
                content=f"Failed to execute '{tool.name}': invalid JSON in arguments: {tool_call.function.arguments}",
                tool_call_id=tool_call.id,
            ))
            continue

        ok, msgs = tool.validate_tool_call_args(ctx, tool_call, args)
        tool_res_messages.extend(msgs)

        if not ok:
            continue

        _ok, msgs = await tool.execute(ctx, tool_call, args)
        tool_res_messages.extend(msgs)

    return tool_res_messages
