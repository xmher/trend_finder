"""
Discovery pipeline — surfaces keywords you don't already know about.

Takes raw trends from collectors and identifies novel keywords that aren't
in the seed database but show signals of relevance to the romantasy/POD niche.
"""

import logging
from datetime import datetime

from analyzer.keywords import KEYWORD_DATABASE, get_all_keywords

logger = logging.getLogger(__name__)

# Flat set for fast lookups
_KNOWN_KEYWORDS: set[str] | None = None


def _get_known_keywords() -> set[str]:
    global _KNOWN_KEYWORDS
    if _KNOWN_KEYWORDS is None:
        _KNOWN_KEYWORDS = {kw.lower() for kw in get_all_keywords()}
    return _KNOWN_KEYWORDS


# Words that signal the keyword is in our niche even if it's not in the database
NICHE_SIGNALS = [
    "romantasy", "romance", "fantasy", "booktok", "bookish", "book",
    "reader", "reading", "fae", "dragon", "enemies", "lovers", "morally grey",
    "spicy", "smut", "dark academia", "villain", "crown", "throne", "court",
    "mate", "bond", "magic", "witch", "fated", "forbidden", "merch",
    "kindle", "colleen", "maas", "yarros", "armentrout", "holly black",
    "fourth wing", "acotar", "print on demand", "etsy", "tshirt", "sticker",
]


def compute_discovery_confidence(
    keyword: str,
    source_type: str,
    engagement: int = 0,
) -> float:
    """
    Score how confident we are that a discovered keyword is relevant.

    source_type values:
        "related_query"  — Google Trends rising query related to a core term
        "trending_search" — Google Trends daily trending (completely unseeded)
        "pinterest_trend" — Pinterest growing/monthly trend
        "pinterest_prediction" — Pinterest predicted trend
        "search_result"  — Found via keyword search on any platform
    """
    kw_lower = keyword.lower()

    # If it's already a known keyword, not a "discovery"
    if kw_lower in _get_known_keywords():
        return -1.0  # signal to skip

    score = 0.0

    # Base confidence from source type
    source_scores = {
        "related_query": 55.0,       # came from related queries to our core terms
        "pinterest_trend": 35.0,     # Pinterest growing trend (unseeded)
        "pinterest_prediction": 40.0, # Pinterest predicted trend
        "trending_search": 15.0,     # Google daily trending (usually noise)
        "search_result": 25.0,       # found via search but not in our DB
    }
    score += source_scores.get(source_type, 10.0)

    # Niche signal matching — does the keyword contain romantasy-adjacent words?
    niche_matches = sum(1 for signal in NICHE_SIGNALS if signal in kw_lower)
    score += min(niche_matches * 12, 36)  # up to +36 for 3+ matches

    # Partial match against seed keywords (looser than exact match)
    partial_matches = 0
    for known in _get_known_keywords():
        # Check if any known keyword is a substring or vice versa
        if len(known) >= 4 and (known in kw_lower or kw_lower in known):
            partial_matches += 1
    score += min(partial_matches * 8, 24)  # up to +24 for 3+ partial matches

    # Engagement bonus (log-scaled)
    if engagement > 0:
        import math
        score += min(math.log10(engagement) * 4, 16)  # up to +16

    return min(score, 100.0)


def extract_discoveries(trends: list[dict]) -> list[dict]:
    """
    Given raw trends from a fetch cycle, identify novel keywords that
    aren't in the seed database but look relevant.

    Each trend dict should have:
        - keyword: str
        - platform: str
        - engagement: int
        - title: str
        - _source_type: str (optional, set by collectors for discovery-capable sources)
        - _source_context: str (optional, human-readable context)

    Returns a list of discovery dicts ready for storage.
    """
    known = _get_known_keywords()
    seen: dict[str, dict] = {}  # deduplicate by keyword

    for t in trends:
        kw = t.get("keyword", "").strip()
        if not kw or len(kw) < 3:
            continue

        kw_lower = kw.lower()

        # Skip if it's a known seed keyword
        if kw_lower in known:
            continue

        source_type = t.get("_source_type", "search_result")
        engagement = t.get("engagement", 0)
        platform = t.get("platform", "unknown")
        context = t.get("_source_context", "")

        confidence = compute_discovery_confidence(kw, source_type, engagement)
        if confidence < 0:
            continue  # already known
        if confidence < 15:
            continue  # too noisy, skip

        if kw_lower in seen:
            # Update existing — boost confidence for cross-platform sighting
            existing = seen[kw_lower]
            existing["confidence"] = min(existing["confidence"] + 10, 100.0)
            existing["engagement"] = max(existing["engagement"], engagement)
            if platform not in existing["platforms"]:
                existing["platforms"].append(platform)
        else:
            seen[kw_lower] = {
                "keyword": kw,
                "source_platform": platform,
                "source_context": context,
                "confidence": round(confidence, 1),
                "engagement": engagement,
                "platforms": [platform],
            }

    # Sort by confidence descending
    discoveries = sorted(seen.values(), key=lambda d: d["confidence"], reverse=True)

    logger.info(f"Discovery pipeline: found {len(discoveries)} novel keywords")
    return discoveries
