"""
Pinterest collector using the official Pinterest API v5.

Searches for romantasy-related pins and trending content.
Requires a Pinterest business account and app.
"""

import logging

import httpx

from analyzer.keywords import get_search_queries
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)

PINTEREST_SEARCH_URL = "https://api.pinterest.com/v5/search/pins"


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
            for query in get_search_queries()[:10]:
                try:
                    params = {
                        "query": query,
                        "page_size": 25,
                    }
                    resp = await client.get(
                        PINTEREST_SEARCH_URL, headers=headers, params=params
                    )

                    if resp.status_code == 429:
                        logger.warning("Pinterest: rate limited, stopping")
                        break

                    if resp.status_code != 200:
                        logger.warning(f"Pinterest: {resp.status_code} for '{query}'")
                        continue

                    data = resp.json()
                    for pin in data.get("items", []):
                        # Pinterest API doesn't expose engagement metrics
                        # directly in search, so we use pin saves as a proxy
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

        logger.info(f"Pinterest: collected {len(trends)} trends")
        return trends
