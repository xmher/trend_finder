from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Trend(Base):
    """A single trend data point collected from a platform."""
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), nullable=False, index=True)       # reddit, twitter, tiktok, pinterest, threads
    keyword = Column(String(256), nullable=False, index=True)        # the trending term / hashtag
    title = Column(String(512), default="")                          # post title or description
    url = Column(String(1024), default="")                           # link to the source
    engagement = Column(Integer, default=0)                          # likes + comments + shares (combined)
    relevance_score = Column(Float, default=0.0)                     # 0-100 romantasy relevance score
    trend_velocity = Column(Float, default=0.0)                      # rate of engagement growth
    category = Column(String(128), default="general")                # trope, aesthetic, character, quote, etc.
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "keyword": self.keyword,
            "title": self.title,
            "url": self.url,
            "engagement": self.engagement,
            "relevance_score": self.relevance_score,
            "trend_velocity": self.trend_velocity,
            "category": self.category,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


class TrendSnapshot(Base):
    """Aggregated trend score over time for tracking trend trajectory."""
    __tablename__ = "trend_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(256), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    score = Column(Float, default=0.0)
    total_engagement = Column(Integer, default=0)
    post_count = Column(Integer, default=0)
    snapshot_at = Column(DateTime, default=datetime.utcnow, index=True)


class DiscoveredKeyword(Base):
    """A keyword surfaced by the discovery pipeline that isn't in the seed database."""
    __tablename__ = "discovered_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(256), nullable=False, unique=True, index=True)
    source_platform = Column(String(32), nullable=False)          # which platform first found it
    source_context = Column(String(512), default="")              # e.g. "rising query related to 'romantasy'"
    confidence = Column(Float, default=0.0)                       # 0-100 how likely this is relevant
    times_seen = Column(Integer, default=1)                       # how many fetch cycles it appeared in
    peak_engagement = Column(Integer, default=0)                  # highest engagement seen
    platforms_seen = Column(String(256), default="")              # comma-separated list of platforms
    status = Column(String(16), default="new", index=True)        # new, promoted, dismissed
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "keyword": self.keyword,
            "source_platform": self.source_platform,
            "source_context": self.source_context,
            "confidence": self.confidence,
            "times_seen": self.times_seen,
            "peak_engagement": self.peak_engagement,
            "platforms_seen": self.platforms_seen.split(",") if self.platforms_seen else [],
            "status": self.status,
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }


class FetchLog(Base):
    """Tracks when each platform was last fetched."""
    __tablename__ = "fetch_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), nullable=False)
    status = Column(String(32), default="success")  # success, error
    message = Column(Text, default="")
    trends_found = Column(Integer, default=0)
    fetched_at = Column(DateTime, default=datetime.utcnow)
