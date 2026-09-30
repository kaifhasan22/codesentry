from pathlib import Path
from types import SimpleNamespace

from app.analyzers import dead_code
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


def test_dead_code_analyzer_scavenges_the_full_inventory_once(tmp_path: Path, monkeypatch):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("value = 1\n", encoding="utf-8")
    second.write_text("other = 2\n", encoding="utf-8")

    class FakeVulture:
        def __init__(self):
            self.calls = []

        def scan(self, source, filename):
            self.calls.append(str(filename))

        def scavenge(self, paths):
            assert paths == []

        def get_unused_code(self, min_confidence=0):
            assert min_confidence == 90
            return [SimpleNamespace(
                filename=first,
                first_lineno=1,
                typ="variable",
                name="value",
                confidence=100,
                message="unused variable 'value'",
            )]

    analyzer = FakeVulture()
    monkeypatch.setattr(dead_code.vulture, "Vulture", lambda: analyzer)

    findings = dead_code.analyze(tmp_path, [first, second])

    assert analyzer.calls == [str(first), str(second)]
    assert len(findings) == 1
    assert findings[0].file_path == "first.py"
