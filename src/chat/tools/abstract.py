from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel

from chat.tools.context import ToolContext
from chat.types import ToolCall, ChatMessage, ChatTool


class ToolProps(BaseModel):
    tool_name: str
    system_prompt: Optional[str] = None
    depends_on: Optional[List[str]] = None


class Tool:
    @property
    def name(self) -> str:
        raise NotImplementedError("property 'name' is not implemented for tool")

    def validate_tool_call_args(
            self,
            ctx: ToolContext,
            tool_call: ToolCall,
            args: Dict[str, Any]
    ) -> Tuple[bool, List[ChatMessage]]:
        raise NotImplementedError(f"method 'validate_tool_call_args' is not implemented for tool {self.name}")

    async def execute(
            self,
            ctx: ToolContext,
            tool_call: ToolCall,
            args: Dict[str, Any]
    ) -> Tuple[bool, List[ChatMessage]]:
        raise NotImplementedError(f"method 'execute' is not implemented for tool {self.name}")

    def into_chat_tool(self) -> ChatTool:
        raise NotImplementedError(f"method 'into_chat_tool' is not implemented for tool {self.name}")

    def props(self) -> ToolProps:
        raise NotImplementedError(f"method 'props' is not implemented for tool {self.name}")
