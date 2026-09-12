from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class RawSearchResult(BaseModel):
    title: str
    url: HttpUrl
    summary: str
    published_date: datetime | None = None
    source_domain: str

class ResearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[RawSearchResult]:
        """Search for information based on a query."""
