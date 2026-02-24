"""
Trend Finder — Romantasy POD trend detection dashboard.

Run with: uvicorn main:app --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from analyzer.scorer import rank_trends
from config import settings
from database import get_db, init_db
from models import DiscoveredKeyword, FetchLog, Trend, TrendSnapshot
from scheduler import create_scheduler, fetch_all_trends

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")

    scheduler = create_scheduler()
    scheduler.start()
    logger.info(f"Scheduler started (every {settings.FETCH_INTERVAL_MINUTES} min)")

    yield

    scheduler.shutdown()


app = FastAPI(title="Trend Finder", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ──────────────────────────── Dashboard ────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ──────────────────────────── API Routes ────────────────────────────


@app.get("/api/trends")
def get_trends(
    db: Session = Depends(get_db),
    platform: str | None = Query(None),
    category: str | None = Query(None),
    min_score: float = Query(0),
    hours: int = Query(168),
    limit: int = Query(100),
):
    """Get trends filtered by platform, category, score, and time range."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(Trend).filter(
        Trend.fetched_at >= cutoff,
        Trend.relevance_score >= min_score,
    )
    if platform:
        query = query.filter(Trend.platform == platform)
    if category:
        query = query.filter(Trend.category == category)

    query = query.order_by(desc(Trend.relevance_score), desc(Trend.engagement))
    results = query.limit(limit).all()

    trend_dicts = [t.to_dict() for t in results]
    ranked = rank_trends(trend_dicts)
    return {"trends": ranked, "count": len(ranked)}


@app.get("/api/trends/top")
def get_top_trends(
    db: Session = Depends(get_db),
    hours: int = Query(168),
    limit: int = Query(20),
):
    """Get top trending keywords aggregated across all platforms."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    results = (
        db.query(
            Trend.keyword,
            func.count(Trend.id).label("post_count"),
            func.sum(Trend.engagement).label("total_engagement"),
            func.max(Trend.relevance_score).label("max_relevance"),
            func.group_concat(Trend.platform.distinct()).label("platforms"),
        )
        .filter(Trend.fetched_at >= cutoff, Trend.relevance_score > 0)
        .group_by(Trend.keyword)
        .order_by(desc("max_relevance"), desc("total_engagement"))
        .limit(limit)
        .all()
    )

    return {
        "trends": [
            {
                "keyword": r.keyword,
                "post_count": r.post_count,
                "total_engagement": r.total_engagement,
                "max_relevance": r.max_relevance,
                "platforms": r.platforms.split(",") if r.platforms else [],
            }
            for r in results
        ]
    }


@app.get("/api/trends/timeline")
def get_trend_timeline(
    db: Session = Depends(get_db),
    keyword: str = Query(...),
    days: int = Query(7),
):
    """Get engagement timeline for a specific keyword."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    results = (
        db.query(TrendSnapshot)
        .filter(TrendSnapshot.keyword == keyword, TrendSnapshot.snapshot_at >= cutoff)
        .order_by(TrendSnapshot.snapshot_at)
        .all()
    )

    return {
        "keyword": keyword,
        "timeline": [
            {
                "date": r.snapshot_at.isoformat(),
                "score": r.score,
                "engagement": r.total_engagement,
                "post_count": r.post_count,
                "platform": r.platform,
            }
            for r in results
        ],
    }


@app.get("/api/platforms")
async def get_platform_status(db: Session = Depends(get_db)):
    """Get the status of each platform collector."""
    from collectors.google_trends import GoogleTrendsCollector
    from collectors.pinterest import PinterestCollector
    from collectors.reddit import RedditCollector
    from collectors.threads import ThreadsCollector
    from collectors.tiktok import TikTokCollector
    from collectors.twitter import TwitterCollector

    collectors = [
        RedditCollector(),
        TwitterCollector(),
        TikTokCollector(),
        PinterestCollector(),
        ThreadsCollector(),
        GoogleTrendsCollector(),
    ]

    platforms = []
    for c in collectors:
        configured = await c.is_configured()

        last_log = (
            db.query(FetchLog)
            .filter(FetchLog.platform == c.platform)
            .order_by(desc(FetchLog.fetched_at))
            .first()
        )

        platforms.append({
            "name": c.platform,
            "configured": configured,
            "last_fetch": last_log.fetched_at.isoformat() if last_log else None,
            "last_status": last_log.status if last_log else None,
            "trends_found": last_log.trends_found if last_log else 0,
        })

    return {"platforms": platforms}


@app.post("/api/fetch")
async def trigger_fetch():
    """Manually trigger a trend fetch from all platforms."""
    asyncio.create_task(fetch_all_trends())
    return {"status": "started", "message": "Trend fetch started in background"}


# ──────────────────────── Discovery Endpoints ────────────────────────


@app.get("/api/discoveries")
def get_discoveries(
    db: Session = Depends(get_db),
    status: str | None = Query(None),
    min_confidence: float = Query(0),
    limit: int = Query(50),
):
    """Get discovered keywords — novel trends not in the seed database."""
    query = db.query(DiscoveredKeyword).filter(
        DiscoveredKeyword.confidence >= min_confidence,
    )
    if status:
        query = query.filter(DiscoveredKeyword.status == status)
    else:
        # By default, exclude dismissed
        query = query.filter(DiscoveredKeyword.status != "dismissed")

    results = (
        query
        .order_by(desc(DiscoveredKeyword.confidence), desc(DiscoveredKeyword.times_seen))
        .limit(limit)
        .all()
    )

    return {
        "discoveries": [d.to_dict() for d in results],
        "count": len(results),
    }


@app.post("/api/discoveries/{discovery_id}/promote")
def promote_discovery(discovery_id: int, db: Session = Depends(get_db)):
    """Mark a discovered keyword as promoted (worth tracking long-term)."""
    disc = db.query(DiscoveredKeyword).filter(DiscoveredKeyword.id == discovery_id).first()
    if not disc:
        return {"error": "Not found"}, 404
    disc.status = "promoted"
    db.commit()
    return {"status": "promoted", "keyword": disc.keyword}


@app.post("/api/discoveries/{discovery_id}/dismiss")
def dismiss_discovery(discovery_id: int, db: Session = Depends(get_db)):
    """Dismiss a discovered keyword as not relevant."""
    disc = db.query(DiscoveredKeyword).filter(DiscoveredKeyword.id == discovery_id).first()
    if not disc:
        return {"error": "Not found"}, 404
    disc.status = "dismissed"
    db.commit()
    return {"status": "dismissed", "keyword": disc.keyword}


@app.get("/api/discoveries/stats")
def get_discovery_stats(db: Session = Depends(get_db)):
    """Get summary stats for the discovery pipeline."""
    total = db.query(func.count(DiscoveredKeyword.id)).scalar() or 0
    new_count = (
        db.query(func.count(DiscoveredKeyword.id))
        .filter(DiscoveredKeyword.status == "new")
        .scalar() or 0
    )
    promoted_count = (
        db.query(func.count(DiscoveredKeyword.id))
        .filter(DiscoveredKeyword.status == "promoted")
        .scalar() or 0
    )
    high_confidence = (
        db.query(func.count(DiscoveredKeyword.id))
        .filter(DiscoveredKeyword.confidence >= 60)
        .scalar() or 0
    )
    return {
        "total": total,
        "new": new_count,
        "promoted": promoted_count,
        "high_confidence": high_confidence,
    }


@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    """Get all trend categories with counts."""
    results = (
        db.query(Trend.category, func.count(Trend.id).label("count"))
        .group_by(Trend.category)
        .order_by(desc("count"))
        .all()
    )
    return {"categories": [{"name": r.category, "count": r.count} for r in results]}
