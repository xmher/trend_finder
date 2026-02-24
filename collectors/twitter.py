"""
Twitter/X collector using the official Twitter API v2.

Searches for romantasy-related tweets and trending hashtags.
Free tier: 1,500 tweets/month read.
"""

import logging
from datetime import datetime, timedelta

import httpx

from analyzer.keywords import get_search_queries
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)

TWITTER_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


class TwitterCollector(BaseCollector):
    platform = "twitter"

    async def is_configured(self) -> bool:
        return bool(settings.TWITTER_BEARER_TOKEN)

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        trends = []
        headers = {"Authorization": f"Bearer {settings.TWITTER_BEARER_TOKEN}"}

        async with httpx.AsyncClient(timeout=30) as client:
            # Search for top romantasy-related tweets
            # Use fewer queries to stay within free tier limits
            for query in get_search_queries()[:8]:
                try:
                    params = {
                        "query": f"{query} -is:retweet lang:en",
                        "max_results": 10,
                        "sort_order": "relevancy",
                        "tweet.fields": "public_metrics,created_at",
                    }
                    resp = await client.get(
                        TWITTER_SEARCH_URL, headers=headers, params=params
                    )

                    if resp.status_code == 429:
                        logger.warning("Twitter: rate limited, stopping")
                        break

                    if resp.status_code != 200:
                        logger.warning(f"Twitter: {resp.status_code} for '{query}'")
                        continue

                    data = resp.json()
                    for tweet in data.get("data", []):
                        metrics = tweet.get("public_metrics", {})
                        engagement = (
                            metrics.get("like_count", 0)
                            + metrics.get("retweet_count", 0)
                            + metrics.get("reply_count", 0)
                            + metrics.get("quote_count", 0)
                        )
                        trends.append(self._make_trend(
                            keyword=query,
                            title=tweet.get("text", "")[:512],
                            url=f"https://twitter.com/i/web/status/{tweet['id']}",
                            engagement=engagement,
                        ))

                except httpx.HTTPError as e:
                    logger.warning(f"Twitter: request failed for '{query}': {e}")

        logger.info(f"Twitter: collected {len(trends)} trends")
        return trends
