"""
Background scheduler that periodically fetches trends from all platforms.
"""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from analyzer.scorer import score_relevance
from collectors.pinterest import PinterestCollector
from collectors.reddit import RedditCollector
from collectors.threads import ThreadsCollector
from collectors.tiktok import TikTokCollector
from collectors.twitter import TwitterCollector
from config import settings
from database import SessionLocal
from models import FetchLog, Trend, TrendSnapshot

logger = logging.getLogger(__name__)

ALL_COLLECTORS = [
    RedditCollector(),
    TwitterCollector(),
    TikTokCollector(),
    PinterestCollector(),
    ThreadsCollector(),
]


async def fetch_all_trends():
    """Run all configured collectors and store results."""
    logger.info("Starting trend fetch cycle...")

    for collector in ALL_COLLECTORS:
        if not await collector.is_configured():
            logger.info(f"Skipping {collector.platform} (not configured)")
            continue

        try:
            raw_trends = await collector.fetch_trends()

            # Score each trend for romantasy relevance
            scored = []
            for t in raw_trends:
                text = f"{t.get('keyword', '')} {t.get('title', '')}"
                relevance, category = score_relevance(text)
                t["relevance_score"] = relevance
                t["category"] = category
                scored.append(t)

            # Persist to database (sync, runs in executor)
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(
                None, _save_trends, collector.platform, scored
            )

            logger.info(f"{collector.platform}: saved {count} trends")

        except Exception as e:
            logger.error(f"{collector.platform}: fetch failed: {e}")
            _log_fetch(collector.platform, "error", str(e), 0)


def _save_trends(platform: str, trends: list[dict]) -> int:
    """Save trends to the database (synchronous)."""
    session = SessionLocal()
    try:
        count = 0
        keyword_stats: dict[str, dict] = {}

        for t in trends:
            trend = Trend(
                platform=t["platform"],
                keyword=t["keyword"],
                title=t.get("title", ""),
                url=t.get("url", ""),
                engagement=t.get("engagement", 0),
                relevance_score=t.get("relevance_score", 0),
                category=t.get("category", "general"),
                fetched_at=t.get("fetched_at", datetime.utcnow()),
            )
            session.add(trend)
            count += 1

            # Aggregate for snapshots
            kw = t["keyword"]
            if kw not in keyword_stats:
                keyword_stats[kw] = {"score": 0, "engagement": 0, "count": 0}
            keyword_stats[kw]["score"] = max(
                keyword_stats[kw]["score"], t.get("relevance_score", 0)
            )
            keyword_stats[kw]["engagement"] += t.get("engagement", 0)
            keyword_stats[kw]["count"] += 1

        # Create snapshots for trend tracking
        for kw, stats in keyword_stats.items():
            snapshot = TrendSnapshot(
                keyword=kw,
                platform=platform,
                score=stats["score"],
                total_engagement=stats["engagement"],
                post_count=stats["count"],
                snapshot_at=datetime.utcnow(),
            )
            session.add(snapshot)

        # Log the fetch
        fetch_log = FetchLog(
            platform=platform,
            status="success",
            message=f"Collected {count} trends",
            trends_found=count,
            fetched_at=datetime.utcnow(),
        )
        session.add(fetch_log)
        session.commit()
        return count

    except Exception as e:
        session.rollback()
        logger.error(f"DB save error for {platform}: {e}")
        _log_fetch(platform, "error", str(e), 0)
        return 0
    finally:
        session.close()


def _log_fetch(platform: str, status: str, message: str, count: int):
    """Log a fetch attempt."""
    session = SessionLocal()
    try:
        log = FetchLog(
            platform=platform, status=status, message=message,
            trends_found=count, fetched_at=datetime.utcnow(),
        )
        session.add(log)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def create_scheduler() -> AsyncIOScheduler:
    """Create the APScheduler instance."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        fetch_all_trends,
        "interval",
        minutes=settings.FETCH_INTERVAL_MINUTES,
        id="fetch_trends",
        name="Fetch trends from all platforms",
        replace_existing=True,
    )
    return scheduler
