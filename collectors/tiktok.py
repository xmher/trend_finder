"""
TikTok collector using the official TikTok Research API.

Searches for romantasy-related videos and trending hashtags.
Requires approved Research API access from TikTok for Developers.
"""

import logging
from datetime import datetime, timedelta

import httpx

from analyzer.keywords import get_search_queries
from collectors.base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)

TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_SEARCH_URL = "https://open.tiktokapis.com/v2/research/video/query/"


class TikTokCollector(BaseCollector):
    platform = "tiktok"
    _access_token: str | None = None

    async def is_configured(self) -> bool:
        return bool(settings.TIKTOK_CLIENT_KEY and settings.TIKTOK_CLIENT_SECRET)

    async def _get_access_token(self, client: httpx.AsyncClient) -> str | None:
        """Get OAuth2 access token using client credentials."""
        if self._access_token:
            return self._access_token

        try:
            resp = await client.post(
                TIKTOK_TOKEN_URL,
                data={
                    "client_key": settings.TIKTOK_CLIENT_KEY,
                    "client_secret": settings.TIKTOK_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200:
                self._access_token = resp.json().get("access_token")
                return self._access_token
            else:
                logger.error(f"TikTok: token request failed: {resp.status_code}")
                return None
        except httpx.HTTPError as e:
            logger.error(f"TikTok: token request error: {e}")
            return None

    async def fetch_trends(self) -> list[dict]:
        if not await self.is_configured():
            return []

        trends = []

        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_access_token(client)
            if not token:
                return []

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d")
            end_date = datetime.utcnow().strftime("%Y%m%d")

            for query in get_search_queries()[:10]:
                try:
                    body = {
                        "query": {
                            "and": [{"operation": "IN", "field_name": "keyword", "field_values": [query]}]
                        },
                        "start_date": start_date,
                        "end_date": end_date,
                        "max_count": 20,
                    }
                    params = {"fields": "id,like_count,comment_count,share_count,view_count,video_description"}

                    resp = await client.post(
                        TIKTOK_SEARCH_URL,
                        headers=headers,
                        json=body,
                        params=params,
                    )

                    if resp.status_code == 429:
                        logger.warning("TikTok: rate limited, stopping")
                        break

                    if resp.status_code != 200:
                        logger.warning(f"TikTok: {resp.status_code} for '{query}'")
                        continue

                    data = resp.json()
                    for video in data.get("data", {}).get("videos", []):
                        engagement = (
                            video.get("like_count", 0)
                            + video.get("comment_count", 0)
                            + video.get("share_count", 0)
                        )
                        trends.append(self._make_trend(
                            keyword=query,
                            title=video.get("video_description", "")[:512],
                            url=f"https://www.tiktok.com/@/video/{video.get('id', '')}",
                            engagement=engagement,
                        ))

                except httpx.HTTPError as e:
                    logger.warning(f"TikTok: request failed for '{query}': {e}")

        logger.info(f"TikTok: collected {len(trends)} trends")
        return trends
