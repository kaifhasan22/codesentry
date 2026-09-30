from __future__ import annotations

from math import ceil

MAX_AI_REVIEW_FINDINGS = 24
AI_BATCH_SIZE = 8
SCAN_SOFT_TIME_LIMIT_SECONDS = 270
SCAN_HARD_TIME_LIMIT_SECONDS = 300
SCAN_STALE_AFTER_SECONDS = SCAN_HARD_TIME_LIMIT_SECONDS + 30


def estimate_static_remaining(file_count: int, source_bytes: int, ai_enabled: bool) -> tuple[int, int]:
    """Return a broad remaining-time range after the repository is prepared."""
    megabytes = source_bytes / (1024 * 1024)
    static_min = 2 + file_count * 0.015 + megabytes * 0.05
    static_max = 8 + file_count * 0.04 + megabytes * 0.25
    ai_max = 45 if ai_enabled else 1
    return max(1, int(static_min)), max(2, int(static_max + ai_max + 10))


def estimate_ai_remaining(findings_count: int, ai_enabled: bool) -> tuple[int, int]:
    if not ai_enabled or findings_count <= 0:
        return 2, 10
    batches = ceil(min(findings_count, MAX_AI_REVIEW_FINDINGS) / AI_BATCH_SIZE)
    return batches * 3 + 2, batches * 15 + 10
