"""
Background scheduler that periodically fetches trends from all platforms.
"""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from analyzer.discovery import extract_discoveries
from analyzer.scorer import score_relevance
from collectors.google_trends import GoogleTrendsCollector
from collectors.pinterest import PinterestCollector
from collectors.reddit import RedditCollector
from collectors.threads import ThreadsCollector
from collectors.tiktok import TikTokCollector
from collectors.twitter import TwitterCollector
from config import settings
from database import SessionLocal
from models import DiscoveredKeyword, FetchLog, Trend, TrendSnapshot

logger = logging.getLogger(__name__)

ALL_COLLECTORS = [
    RedditCollector(),
    TwitterCollector(),
    TikTokCollector(),
    PinterestCollector(),
    ThreadsCollector(),
    GoogleTrendsCollector(),
]


async def fetch_all_trends():
    """Run all configured collectors and store results."""
    logger.info("Starting trend fetch cycle...")

    # Accumulate all raw trends for discovery pipeline
    all_raw_trends: list[dict] = []

    for collector in ALL_COLLECTORS:
        if not await collector.is_configured():
            logger.info(f"Skipping {collector.platform} (not configured)")
            continue

        try:
            raw_trends = await collector.fetch_trends()

            # Keep raw copies for discovery (before scoring mutates them)
            all_raw_trends.extend(raw_trends)

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

    # Run discovery pipeline on all collected trends
    try:
        discoveries = extract_discoveries(all_raw_trends)
        if discoveries:
            loop = asyncio.get_event_loop()
            disc_count = await loop.run_in_executor(
                None, _save_discoveries, discoveries
            )
            logger.info(f"Discovery pipeline: saved {disc_count} new/updated keywords")
    except Exception as e:
        logger.error(f"Discovery pipeline failed: {e}")


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


def _save_discoveries(discoveries: list[dict]) -> int:
    """Save or update discovered keywords in the database."""
    session = SessionLocal()
    try:
        count = 0
        for d in discoveries:
            kw_lower = d["keyword"].lower().strip()
            existing = (
                session.query(DiscoveredKeyword)
                .filter(DiscoveredKeyword.keyword == kw_lower)
                .first()
            )

            platforms_str = ",".join(d.get("platforms", [d["source_platform"]]))

            if existing:
                # Update: bump times_seen, update confidence, track platforms
                existing.times_seen += 1
                existing.last_seen_at = datetime.utcnow()
                existing.peak_engagement = max(
                    existing.peak_engagement, d.get("engagement", 0)
                )
                # Merge platforms
                old_platforms = set(existing.platforms_seen.split(",")) if existing.platforms_seen else set()
                new_platforms = set(d.get("platforms", []))
                existing.platforms_seen = ",".join(old_platforms | new_platforms)
                # Boost confidence for repeat sightings (up to cap)
                repeat_boost = min(existing.times_seen * 5, 25)
                existing.confidence = min(
                    max(existing.confidence, d["confidence"]) + repeat_boost, 100.0
                )
            else:
                # New discovery
                discovered = DiscoveredKeyword(
                    keyword=kw_lower,
                    source_platform=d["source_platform"],
                    source_context=d.get("source_context", ""),
                    confidence=d["confidence"],
                    times_seen=1,
                    peak_engagement=d.get("engagement", 0),
                    platforms_seen=platforms_str,
                    status="new",
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                session.add(discovered)
                count += 1

        session.commit()
        return count

    except Exception as e:
        session.rollback()
        logger.error(f"DB save error for discoveries: {e}")
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
