from dataclasses import dataclass

import aiohttp


@dataclass
class ToolContext:
    session: aiohttp.ClientSession
