"""
Trend scoring engine.

Scores content by relevance to the romantasy POD niche and estimates
trend velocity (how fast something is growing).
"""

import re

from analyzer.keywords import KEYWORD_DATABASE


def score_relevance(text: str) -> tuple[float, str]:
    """
    Score how relevant a piece of text is to the romantasy POD niche.

    Returns (score 0-100, best matching category).
    """
    if not text:
        return 0.0, "general"

    text_lower = text.lower()
    total_score = 0.0
    max_weight = 0
    best_category = "general"

    for category, entries in KEYWORD_DATABASE.items():
        for keyword, weight in entries:
            if keyword in text_lower:
                total_score += weight * 10
                if weight > max_weight:
                    max_weight = weight
                    best_category = category

    # Cap at 100
    return min(total_score, 100.0), best_category


def extract_keywords(text: str) -> list[str]:
    """Extract all matching romantasy keywords found in text."""
    if not text:
        return []

    text_lower = text.lower()
    found = []
    for entries in KEYWORD_DATABASE.values():
        for keyword, _weight in entries:
            if keyword in text_lower:
                found.append(keyword)
    return found


def estimate_velocity(current_engagement: int, age_hours: float) -> float:
    """
    Estimate trend velocity: engagement per hour.
    Higher velocity = faster-growing trend.
    """
    if age_hours <= 0:
        age_hours = 1.0
    return current_engagement / age_hours


def rank_trends(trends: list[dict]) -> list[dict]:
    """
    Rank a list of trend dicts by a composite score combining
    relevance and engagement.
    """
    for t in trends:
        relevance = t.get("relevance_score", 0)
        engagement = t.get("engagement", 0)
        # Log-scale engagement to prevent viral outliers from dominating
        import math
        eng_score = math.log10(max(engagement, 1)) * 10
        t["composite_score"] = round(relevance * 0.6 + eng_score * 0.4, 1)

    return sorted(trends, key=lambda t: t["composite_score"], reverse=True)
