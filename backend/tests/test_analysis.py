from pathlib import Path

from app.services.analysis import health_score, run_static_analysis


def test_analysis_finds_eval_and_secret(tmp_path: Path):
    file = tmp_path / "bad.py"
    file.write_text(
        "API_KEY = '1234567890abcdef'\n"
        "def dangerous(x):\n"
        "    return eval(x)\n",
        encoding="utf-8",
    )
    findings = run_static_analysis(tmp_path)
    titles = {item.title for item in findings}
    assert "Use of eval()" in titles
    assert "Potential hardcoded credential" in titles
    assert health_score(findings) < 100
