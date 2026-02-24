"""
Threads collector using the Meta Threads API.

Searches for romantasy-related posts on Threads.
Requires a Meta developer app with Threads API product enabled.
"""

import logging

import httpx

from analyzer.keywords import get_search_queries
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)

THREADS_SEARCH_URL = "https://graph.threads.net/v1.0"


class ThreadsCollector(BaseCollector):
    platform = "threads"

    async def is_configured(self) -> bool:
        return bool(settings.THREADS_ACCESS_TOKEN)

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        trends = []

        async with httpx.AsyncClient(timeout=30) as client:
            # The Threads API currently supports reading a user's own posts
            # and searching by hashtag. We search hashtags relevant to romantasy.
            for query in get_search_queries()[:10]:
                try:
                    # Search via hashtag endpoint
                    hashtag = query.replace(" ", "").lower()
                    resp = await client.get(
                        f"{THREADS_SEARCH_URL}/tags/{hashtag}/threads",
                        params={
                            "fields": "id,text,timestamp,like_count,reply_count",
                            "access_token": settings.THREADS_ACCESS_TOKEN,
                            "limit": 25,
                        },
                    )

                    if resp.status_code == 429:
                        logger.warning("Threads: rate limited, stopping")
                        break

                    if resp.status_code != 200:
                        logger.warning(f"Threads: {resp.status_code} for '{query}'")
                        continue

                    data = resp.json()
                    for post in data.get("data", []):
                        engagement = (
                            post.get("like_count", 0)
                            + post.get("reply_count", 0)
                        )
                        trends.append(self._make_trend(
                            keyword=query,
                            title=post.get("text", "")[:512],
                            url=f"https://www.threads.net/post/{post.get('id', '')}",
                            engagement=engagement,
                        ))

                except httpx.HTTPError as e:
                    logger.warning(f"Threads: request failed for '{query}': {e}")

        logger.info(f"Threads: collected {len(trends)} trends")
        return trends
