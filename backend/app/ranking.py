"""
Composite search ranking for sort=relevance, layering on top of --
never modifying -- score_job(). Factors: relevance score, recency,
salary presence, and (if a profile_id is supplied) resume match %.
Purely a sort-key computation, nothing persisted.
"""
from datetime import datetime, timezone


def composite_rank(row, base_score: int, match_percent: int = None) -> float:
    rank = base_score * 1.0

    if row.created_at:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - created).days
        recency_bonus = max(0, 10 - age_days * 0.3)  # newer jobs get a small nudge, decaying over ~30 days
        rank += recency_bonus

    if row.salary and row.salary.strip():
        rank += 3  # small nudge for listed salary -- a data-quality/completeness signal

    if match_percent is not None:
        rank += match_percent * 0.5  # resume match, when available, weighted meaningfully but not dominant

    return rank
