"""
Pinterest collector using the official Pinterest API v5.

Uses TWO approaches:
1. Trends endpoint — top trending keywords by region (no search needed)
2. Pin search — search for romantasy-related pins

Requires a Pinterest business account and developer app.
"""

import logging

import httpx

from analyzer.keywords import get_search_queries
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)

PINTEREST_BASE = "https://api.pinterest.com/v5"
PINTEREST_TRENDS_URL = f"{PINTEREST_BASE}/trends/keywords/US/top/growing"
PINTEREST_SEARCH_URL = f"{PINTEREST_BASE}/search/pins"


class PinterestCollector(BaseCollector):
    platform = "pinterest"

    async def is_configured(self) -> bool:
        return bool(settings.PINTEREST_ACCESS_TOKEN)

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        trends = []
        headers = {"Authorization": f"Bearer {settings.PINTEREST_ACCESS_TOKEN}"}

        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Fetch trending keywords (the real gold — includes predictions)
            trends.extend(await self._fetch_trending_keywords(client, headers))

            # 2. Search for romantasy-specific pins
            trends.extend(await self._search_pins(client, headers))

        logger.info(f"Pinterest: collected {len(trends)} trends")
        return trends

    async def _fetch_trending_keywords(
        self, client: httpx.AsyncClient, headers: dict
    ) -> list[dict]:
        """Fetch top growing trends from Pinterest's trends endpoint."""
        trends = []
        try:
            # Fetch growing trends — these are keywords gaining momentum
            resp = await client.get(
                PINTEREST_TRENDS_URL,
                headers=headers,
                params={"include_predictions": "true", "limit": 50},
            )

            if resp.status_code != 200:
                logger.warning(f"Pinterest trends: {resp.status_code}")
                return []

            data = resp.json()
            for trend in data.get("trends", []):
                keyword = trend.get("keyword", "")
                # Pinterest gives normalized search volume
                engagement = trend.get("value", 0)
                trends.append(self._make_trend(
                    keyword=keyword,
                    title=f"Pinterest Trending: {keyword}",
                    url=f"https://www.pinterest.com/search/pins/?q={keyword.replace(' ', '%20')}",
                    engagement=engagement,
                ))

        except httpx.HTTPError as e:
            logger.warning(f"Pinterest trends request failed: {e}")

        # Also try monthly trends
        try:
            monthly_url = f"{PINTEREST_BASE}/trends/keywords/US/top/monthly"
            resp = await client.get(
                monthly_url,
                headers=headers,
                params={"limit": 25},
            )
            if resp.status_code == 200:
                data = resp.json()
                for trend in data.get("trends", []):
                    keyword = trend.get("keyword", "")
                    engagement = trend.get("value", 0)
                    trends.append(self._make_trend(
                        keyword=keyword,
                        title=f"Pinterest Monthly Trend: {keyword}",
                        url=f"https://www.pinterest.com/search/pins/?q={keyword.replace(' ', '%20')}",
                        engagement=engagement,
                    ))
        except httpx.HTTPError as e:
            logger.warning(f"Pinterest monthly trends failed: {e}")

        return trends

    async def _search_pins(
        self, client: httpx.AsyncClient, headers: dict
    ) -> list[dict]:
        """Search for romantasy-related pins."""
        trends = []

        for query in get_search_queries()[:10]:
            try:
                params = {"query": query, "page_size": 25}
                resp = await client.get(
                    PINTEREST_SEARCH_URL, headers=headers, params=params
                )

                if resp.status_code == 429:
                    logger.warning("Pinterest: rate limited, stopping search")
                    break
                if resp.status_code != 200:
                    logger.warning(f"Pinterest: {resp.status_code} for '{query}'")
                    continue

                data = resp.json()
                for pin in data.get("items", []):
                    engagement = pin.get("save_count", 0)
                    title = pin.get("title", "") or pin.get("description", "")
                    pin_id = pin.get("id", "")
                    trends.append(self._make_trend(
                        keyword=query,
                        title=title[:512],
                        url=f"https://www.pinterest.com/pin/{pin_id}/",
                        engagement=engagement,
                    ))

            except httpx.HTTPError as e:
                logger.warning(f"Pinterest: request failed for '{query}': {e}")

        return trends
