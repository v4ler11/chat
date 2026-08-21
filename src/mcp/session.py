import asyncio
import time
from typing import Any


class Session:
    def __init__(self, session_id: str):
        self.id = session_id
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.msg_queue: asyncio.Queue = asyncio.Queue()
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    def touch(self):
        self.last_accessed = time.time()

    def enqueue_message(self, message: Any):
        if not self._active:
            return

        self.msg_queue.put_nowait(message)

    def terminate(self):
        self._active = False
        while not self.msg_queue.empty():
            try:
                self.msg_queue.get_nowait()
            except Exception:
                pass
