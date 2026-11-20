from abc import ABC, abstractmethod
from typing import AsyncIterable

from app.types import AppStreamResponse


class StreamAgent(ABC):
    @abstractmethod
    async def astream(
        self, query: str, context_id: str
    ) -> AsyncIterable[AppStreamResponse]:
        pass
