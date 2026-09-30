"""Deterministic report calculations. AI fields are never read here."""
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from app.services.redaction import redact

SEVERITIES = ("critical", "high", "medium", "low", "info")
PRIORITY_VERSION = "1"


def prioritize(issue) -> dict:
    evidence = getattr(issue, "analyzer_metadata", None) or getattr(issue, "evidence", None) or {}
    score = {"critical": 70, "high": 45, "medium": 25, "low": 8, "info": 0}.get(issue.severity, 0)
    reasons = [f"{issue.severity.capitalize()} analyzer severity: {score} points"]
    if issue.category == "security":
        score += 15
        reasons.append("Security review relevance: +15")
    complexity = evidence.get("cyclomatic_complexity", 0)
    if issue.category == "complexity" and isinstance(complexity, (int, float)) and complexity >= 20:
        bonus = 10 if complexity >= 30 else 5
        score += bonus
        reasons.append(f"Measured cyclomatic complexity {complexity}: +{bonus}")
    confidence = evidence.get("confidence")
    if isinstance(confidence, (int, float)) and 90 <= confidence <= 100:
        bonus = 8 if confidence == 100 else 4
        score += bonus
        reasons.append(f"Analyzer heuristic confidence {confidence}%: +{bonus}")
    path = PurePosixPath(issue.file_path)
    if any(p.lower() in {"tests", "test", "testing", "fixtures", "examples", "docs"} for p in path.parts) or path.name.startswith("test_"):
        score -= 8
        reasons.append("Test/example/documentation path context: −8 (still requires review)")
    score = max(0, min(100, score))
    priority = "p1" if score >= 75 else "p2" if score >= 50 else "p3" if score >= 25 else "p4"
    return {"priority": priority, "priority_score": score, "priority_reasons": reasons}


def issue_payload(issue) -> dict:
    fields = ("id", "category", "severity", "title", "message", "file_path", "line", "snippet", "ai_explanation", "fix_suggestion")
    return {**{name: redact(getattr(issue, name)) if isinstance(getattr(issue, name), str) else getattr(issue, name) for name in fields}, **prioritize(issue)}


def report_insights(issues) -> dict:
    issues = list(issues)
    ranked = sorted(issues, key=lambda i: (-prioritize(i)["priority_score"], i.file_path, i.line or 0, i.id))
    grouped = defaultdict(list)
    for issue in issues:
        grouped[issue.file_path].append(issue)
    hotspots = []
    for path, items in grouped.items():
        counts = Counter(i.severity for i in items)
        meaningful = sum({"critical": 16, "high": 8, "medium": 3}.get(i.severity, 0) * (1.5 if i.category == "security" else 1) for i in items)
        weight = meaningful + min(2, counts["low"] * 0.25) + min(0.25, counts["info"] * 0.05)
        hotspots.append({"file_path": path, "finding_count": len(items), "severity_counts": {s: counts[s] for s in SEVERITIES}, "weight": round(weight, 2)})
    hotspots.sort(key=lambda h: (-h["weight"], h["file_path"]))
    return {"priority_version": PRIORITY_VERSION, "top_issue_ids": [i.id for i in ranked[:5]], "hotspots": hotspots}
