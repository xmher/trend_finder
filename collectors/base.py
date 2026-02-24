"""Base collector interface that all platform collectors implement."""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseCollector(ABC):
    """Base class for platform trend collectors."""

    platform: str = "unknown"

    @abstractmethod
    async def is_configured(self) -> bool:
        """Return True if this collector has valid API credentials."""
        ...

    @abstractmethod
    async def fetch_trends(self) -> list[dict]:
        """
        Fetch trending content from the platform.

        Returns a list of dicts with keys:
            - platform: str
            - keyword: str
            - title: str
            - url: str
            - engagement: int
            - fetched_at: datetime
        """
        ...

    def _make_trend(
        self,
        keyword: str,
        title: str = "",
        url: str = "",
        engagement: int = 0,
    ) -> dict:
        return {
            "platform": self.platform,
            "keyword": keyword,
            "title": title[:512],
            "url": url[:1024],
            "engagement": engagement,
            "fetched_at": datetime.utcnow(),
        }
