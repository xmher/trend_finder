"""
Google Trends collector using the unofficial pytrends library.

No API key required. Provides search interest data over time.
Rate limits: ~10 requests/minute (Google may throttle with 429s).
"""

import asyncio
import logging
from datetime import datetime

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    platform = "google_trends"

    async def is_configured(self) -> bool:
        # Always available — no API key needed
        try:
            from pytrends.request import TrendReq  # noqa: F401
            return True
        except ImportError:
            logger.warning("Google Trends: pytrends not installed (pip install pytrends)")
            return False

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    def _fetch_sync(self) -> list[dict]:
        from pytrends.request import TrendReq

        trends = []

        try:
            pytrends = TrendReq(hl="en-US", tz=360)

            # 1. Get related queries for core romantasy terms
            core_terms = [
                "romantasy",
                "fantasy romance books",
                "booktok",
                "enemies to lovers",
                "fourth wing",
            ]

            # Google Trends allows max 5 keywords at once
            pytrends.build_payload(core_terms, cat=0, timeframe="now 7-d", geo="US")

            # Interest over time — gives us relative search volume
            try:
                interest = pytrends.interest_over_time()
                if not interest.empty:
                    for keyword in core_terms:
                        if keyword in interest.columns:
                            latest = int(interest[keyword].iloc[-1])
                            avg = int(interest[keyword].mean())
                            trends.append(self._make_trend(
                                keyword=keyword,
                                title=f"Google search interest: {keyword} (latest: {latest}, avg: {avg})",
                                url=f"https://trends.google.com/trends/explore?q={keyword.replace(' ', '%20')}&geo=US",
                                engagement=latest,
                            ))
            except Exception as e:
                logger.warning(f"Google Trends interest_over_time failed: {e}")

            # 2. Get related queries (reveals emerging terms)
            try:
                related = pytrends.related_queries()
                for term in core_terms:
                    if term in related and related[term]["rising"] is not None:
                        rising = related[term]["rising"]
                        for _, row in rising.head(10).iterrows():
                            query_text = row.get("query", "")
                            value = int(row.get("value", 0))
                            trend = self._make_trend(
                                keyword=query_text,
                                title=f"Rising search: '{query_text}' (related to '{term}')",
                                url=f"https://trends.google.com/trends/explore?q={query_text.replace(' ', '%20')}&geo=US",
                                engagement=value,
                            )
                            trend["_source_type"] = "related_query"
                            trend["_source_context"] = f"Rising query related to '{term}'"
                            trends.append(trend)
            except Exception as e:
                logger.warning(f"Google Trends related_queries failed: {e}")

            # 3. Trending searches (daily trending in US)
            try:
                trending = pytrends.trending_searches(pn="united_states")
                for _, row in trending.head(20).iterrows():
                    query_text = row.iloc[0] if len(row) > 0 else ""
                    if query_text:
                        trend = self._make_trend(
                            keyword=str(query_text),
                            title=f"Trending search: {query_text}",
                            url=f"https://trends.google.com/trends/explore?q={str(query_text).replace(' ', '%20')}&geo=US",
                            engagement=0,
                        )
                        trend["_source_type"] = "trending_search"
                        trend["_source_context"] = "Google daily trending search (US)"
                        trends.append(trend)
            except Exception as e:
                logger.warning(f"Google Trends trending_searches failed: {e}")

        except Exception as e:
            logger.error(f"Google Trends: {e}")

        logger.info(f"Google Trends: collected {len(trends)} trends")
        return trends
