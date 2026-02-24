"""
Reddit collector using the official Reddit API via PRAW.

Monitors romantasy-related subreddits for trending posts.
Free tier: 100 requests/minute.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import praw
from praw.exceptions import PRAWException

from analyzer.keywords import get_search_queries, get_subreddits
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    platform = "reddit"

    async def is_configured(self) -> bool:
        return bool(settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET)

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        # PRAW is synchronous, so run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    def _fetch_sync(self) -> list[dict]:
        trends = []
        try:
            reddit = praw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT,
            )

            # 1. Monitor hot posts in target subreddits
            for sub_name in get_subreddits():
                try:
                    subreddit = reddit.subreddit(sub_name)
                    for post in subreddit.hot(limit=25):
                        engagement = post.score + post.num_comments
                        trends.append(self._make_trend(
                            keyword=sub_name.lower(),
                            title=post.title,
                            url=f"https://reddit.com{post.permalink}",
                            engagement=engagement,
                        ))
                except Exception as e:
                    logger.warning(f"Reddit: failed to fetch r/{sub_name}: {e}")

            # 2. Search for romantasy keywords across all of Reddit
            for query in get_search_queries()[:10]:  # limit to avoid rate limits
                try:
                    for post in reddit.subreddit("all").search(
                        query, sort="hot", time_filter="week", limit=10
                    ):
                        engagement = post.score + post.num_comments
                        trends.append(self._make_trend(
                            keyword=query,
                            title=post.title,
                            url=f"https://reddit.com{post.permalink}",
                            engagement=engagement,
                        ))
                except Exception as e:
                    logger.warning(f"Reddit: search failed for '{query}': {e}")

        except PRAWException as e:
            logger.error(f"Reddit API error: {e}")

        logger.info(f"Reddit: collected {len(trends)} trends")
        return trends
