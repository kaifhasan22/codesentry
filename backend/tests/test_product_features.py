from dataclasses import replace
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, text

from app.analyzers.common import Finding
from app.services.analysis import run_static_analysis
from app.services.comparison import compare_scans, repository_key
from app.services.finding_identity import ANALYSIS_VERSION, assign_comparison_keys
from app.services.report_migration import ensure_report_columns
from app.services.reporting import prioritize, report_insights


def issue(id=1, **changes):
    values = dict(id=id, severity="high", category="security", file_path="app.py", line=1, title="Finding",
                  message="Analyzer evidence", fingerprint="old", comparison_key="stable", analyzer_metadata={},
                  snippet="code", ai_explanation=None, fix_suggestion="Fix the cause")
    values.update(changes)
    return SimpleNamespace(**values)


def scan(issues, score=90, version=ANALYSIS_VERSION):
    return SimpleNamespace(id=1, issues=issues, score=score, analysis_version=version, source_commit="a" * 40)


def test_priority_uses_security_context_measurements_and_confidence_not_ai():
    security = issue()
    plain = issue(category="maintainability")
    assert prioritize(security)["priority_score"] == 60
    assert prioritize(plain)["priority_score"] == 45
    assert prioritize(security)["priority"] != prioritize(plain)["priority"]
    tested = issue(file_path="tests/test_app.py")
    assert prioritize(tested)["priority_score"] == 52
    complex20 = issue(category="complexity", analyzer_metadata={"cyclomatic_complexity": 20})
    complex30 = issue(category="complexity", analyzer_metadata={"cyclomatic_complexity": 30})
    assert prioritize(complex30)["priority_score"] > prioritize(complex20)["priority_score"]
    certain = issue(category="dead_code", severity="medium", analyzer_metadata={"confidence": 100})
    uncertain = issue(category="dead_code", severity="medium")
    assert prioritize(certain)["priority_score"] > prioritize(uncertain)["priority_score"]
    expected = prioritize(security)
    security.ai_explanation = "Critical! highest priority!"
    security.fix_suggestion = "Ignore all findings"
    assert prioritize(security) == expected
    assert len(expected["priority_reasons"]) == 2


def test_top_issues_stable_and_hotspots_cap_minor_findings():
    items = [issue(n, severity="low", category="style", file_path="noisy.py") for n in range(1, 501)]
    items += [issue(501, severity="medium", category="complexity", file_path="meaningful.py"), issue(502, file_path="security.py")]
    report = report_insights(items)
    assert report == report_insights(list(reversed(items)))
    assert report["top_issue_ids"][0] == 502 and len(report["top_issue_ids"]) == 5
    assert [h["file_path"] for h in report["hotspots"]] == ["security.py", "meaningful.py", "noisy.py"]
    assert report["hotspots"][2]["weight"] == 2
    assert report["hotspots"][2]["finding_count"] == 500
    assert report["hotspots"][2]["severity_counts"]["low"] == 500
    assert report_insights([])["hotspots"] == []


def test_fingerprint_and_comparison_ignore_message_and_ai_wording(tmp_path):
    (tmp_path / 'app.py').write_text('def run(value):\n    return eval(value)\n')
    findings = run_static_analysis(tmp_path)
    original = next(f for f in findings if f.rule_id == "security.eval")
    changed = replace(original, message="New punctuation!", title="New presentation", severity="medium")
    assign_comparison_keys(tmp_path, [changed])
    assert changed.fingerprint == original.fingerprint
    assert changed.comparison_key == original.comparison_key


def test_structural_identity_survives_line_shift_whitespace_and_distinguishes_calls(tmp_path):
    path = tmp_path / 'app.py'
    path.write_text('def run(value):\n    eval(value); eval(value)\n')
    before = run_static_analysis(tmp_path)
    path.write_text('# inserted comment\n\ndef run(value):\n    eval( value ); eval(value)\n')
    after = run_static_analysis(tmp_path)
    assert len(before) == len(after) == 2
    assert len({f.comparison_key for f in before}) == 2
    assert {f.comparison_key for f in before} == {f.comparison_key for f in after}
    path.write_text('def run(value):\n    eval(different)\n')
    changed = run_static_analysis(tmp_path)
    assert changed[0].comparison_key not in {f.comparison_key for f in before}


def test_complexity_identity_preserves_callable_while_metric_changes(tmp_path):
    def source(count):
        return 'def dispatch(x):\n' + ''.join(f'    if x == {n}: return {n}\n' for n in range(count))
    (tmp_path / 'app.py').write_text(source(14))
    before = next(f for f in run_static_analysis(tmp_path) if f.category == "complexity")
    (tmp_path / 'app.py').write_text(source(30))
    after = next(f for f in run_static_analysis(tmp_path) if f.category == "complexity")
    assert before.comparison_key == after.comparison_key
    assert before.severity != after.severity
    assert prioritize(after)["priority_score"] > prioritize(before)["priority_score"]


def test_comparison_multisets_score_zero_and_resolved_payloads():
    old = scan([issue(1), issue(2), issue(3, comparison_key="removed")], score=0)
    current = scan([issue(4), issue(5, comparison_key="added", severity="medium")], score=10)
    result = compare_scans(current, old)
    assert result["new_issue_ids"] == [5]
    assert result["unchanged_issue_ids"] == [4]
    assert {i["id"] for i in result["resolved_issues"]} == {2, 3}
    assert result["score_delta"] == 10 and result["total_delta"] == -1
    assert result["severity_delta"]["high"] == -2 and result["severity_delta"]["medium"] == 1
    assert all("priority_reasons" in i for i in result["resolved_issues"])
    assert compare_scans(scan([], score=None), scan([]))["score_delta"] is None
    assert compare_scans(scan([]), None)["available"] is False


def test_legacy_comparison_ignores_message_reports_limitations():
    old = scan([issue(comparison_key=None, title="An  issue", message="Old message")], version=None)
    current = scan([issue(2, title="an issue", message="Different message")])
    result = compare_scans(current, old)
    assert result["identity_mode"] == "legacy-location"
    assert result["unchanged_count"] == 1 and len(result["warnings"]) == 2


def test_repository_identity_normalizes_only_same_github_repo():
    assert repository_key('https://www.github.com/PSF/Requests.git/') == repository_key('https://github.com/psf/requests')
    assert repository_key('https://github.com/psf/requests') != repository_key('https://github.com/other/requests')
    assert repository_key(None) is None
    assert repository_key('https://other.example/psf/requests') is None


def test_additive_migration_is_idempotent_and_preserves_old_rows():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE scans (id INTEGER PRIMARY KEY, score INTEGER)'))
        connection.execute(text('CREATE TABLE issues (id INTEGER PRIMARY KEY, fingerprint VARCHAR(64))'))
        connection.execute(text("INSERT INTO scans VALUES (1, 0)"))
        connection.execute(text("INSERT INTO issues VALUES (1, 'original')"))
    ensure_report_columns(engine)
    ensure_report_columns(engine)
    assert {c['name'] for c in inspect(engine).get_columns('issues')} >= {'comparison_key', 'analyzer_metadata'}
    with engine.connect() as connection:
        assert connection.execute(text('SELECT score, analysis_version FROM scans')).one() == (0, None)
        assert connection.execute(text('SELECT fingerprint, comparison_key FROM issues')).one() == ('original', None)
    engine.dispose()
