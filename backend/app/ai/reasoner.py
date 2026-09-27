from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from app.analyzers.common import Finding
from app.config import get_settings


class Review(BaseModel):
    fingerprint: str
    severity: str = Field(pattern="^(info|low|medium|high|critical)$")
    confidence: float = Field(ge=0, le=1)
    is_false_positive: bool
    explanation: str
    fix_suggestion: str


class ReviewBatch(BaseModel):
    reviews: list[Review]


SYSTEM_PROMPT = """
You are CodeSentry, a senior Python security and maintainability reviewer.
Your job is to prioritize existing static-analysis findings using the supplied code context.
Do not invent issues. Do not claim exploitability unless the provided context supports it.
For each finding, decide whether it is a likely true issue or false positive, assign practical severity,
and explain the production impact in plain English. Give a concrete fix appropriate to the shown code.
Return only the requested structured output.
""".strip()


def _build_prompt(findings: list[Finding]) -> str:
    parts = ["Review these static-analysis findings. The fingerprint must be echoed exactly.\n"]
    for finding in findings:
        parts.append(
            "\n".join(
                [
                    f"FINGERPRINT: {finding.fingerprint}",
                    f"CATEGORY: {finding.category}",
                    f"TITLE: {finding.title}",
                    f"RAW_SEVERITY: {finding.severity}",
                    f"FILE: {finding.file_path}",
                    f"LINE: {finding.line}",
                    f"MESSAGE: {finding.message}",
                    "SNIPPET:",
                    finding.snippet or "(no snippet)",
                    "---",
                ]
            )
        )
    return "\n".join(parts)


def review_findings(findings: Iterable[Finding], batch_size: int = 8) -> dict[str, Review]:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {}

    try:
        from anthropic import Anthropic
    except ImportError:
        return {}

    client = Anthropic(api_key=settings.anthropic_api_key, timeout=20.0, max_retries=1)
    findings_list = list(findings)
    reviews: dict[str, Review] = {}

    for i in range(0, len(findings_list), batch_size):
        batch = findings_list[i : i + batch_size]
        try:
            response = client.messages.parse(
                model=settings.anthropic_model,
                max_tokens=2500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_prompt(batch)}],
                output_format=ReviewBatch,
            )
            parsed = response.parsed_output
            if not parsed:
                continue
            for review in parsed.reviews:
                reviews[review.fingerprint] = review
        except Exception:
            # AI enrichment is best-effort. Raw analyzer results remain authoritative fallback data.
            continue

    return reviews
