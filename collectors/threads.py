"""
Threads collector using the Meta Threads API.

Uses the keyword search endpoint to find romantasy-related posts.
Requires a Meta developer app with Threads API product enabled.

Rate limit: 500 search queries per rolling 7-day window (~71/day).
"""

import logging

import httpx

from analyzer.keywords import get_search_queries
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)

THREADS_API_BASE = "https://graph.threads.net/v1.0"


class ThreadsCollector(BaseCollector):
    platform = "threads"

    async def is_configured(self) -> bool:
        return bool(settings.THREADS_ACCESS_TOKEN)

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        trends = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Use keyword search endpoint (added late 2024)
            # Limited to ~71 queries/day (500/week rolling)
            for query in get_search_queries()[:8]:
                try:
                    resp = await client.get(
                        f"{THREADS_API_BASE}/search",
                        params={
                            "q": query,
                            "fields": "id,text,timestamp,like_count,reply_count,repost_count",
                            "access_token": settings.THREADS_ACCESS_TOKEN,
                            "limit": 25,
                        },
                    )

                    if resp.status_code == 429:
                        logger.warning("Threads: rate limited (500/week cap), stopping")
                        break

                    if resp.status_code != 200:
                        logger.warning(f"Threads: {resp.status_code} for '{query}'")
                        continue

                    data = resp.json()
                    for post in data.get("data", []):
                        engagement = (
                            post.get("like_count", 0)
                            + post.get("reply_count", 0)
                            + post.get("repost_count", 0)
                        )
                        post_id = post.get("id", "")
                        trends.append(self._make_trend(
                            keyword=query,
                            title=post.get("text", "")[:512],
                            url=f"https://www.threads.net/post/{post_id}",
                            engagement=engagement,
                        ))

                except httpx.HTTPError as e:
                    logger.warning(f"Threads: request failed for '{query}': {e}")

        logger.info(f"Threads: collected {len(trends)} trends")
        return trends
