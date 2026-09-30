from dataclasses import replace
from types import SimpleNamespace
import json
import sys

import pytest
from billiard.exceptions import SoftTimeLimitExceeded
from pydantic import ValidationError

from app.ai import reasoner
from app.analyzers import common, complexity, dead_code, security, style
from app.analyzers.common import Finding
from app.services.analysis import deduplicate_findings, health_score, health_score_breakdown


def finding(severity="low", line=1, **kwargs):
    return Finding(category="style", severity=severity, title="A finding", message="Analyzer evidence",
                   file_path="sample.py", line=line, rule_id="test.rule", fix_suggestion="Fix the cause", **kwargs)


def analyze_source(tmp_path, analyzer, source, filename="sample.py"):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return analyzer.analyze(tmp_path)


@pytest.mark.parametrize("source, rules", [
    ("import pickle as p\np.loads(data)\np.load(stream)", ["security.pickle"] * 2),
    ("from pickle import loads as restore\nrestore(data)", ["security.pickle"]),
    ("import pickle as p\np.loads(p.dumps(obj))", []),
    ("import pickle as p\np.loads(p.dumps(obj) + untrusted)", ["security.pickle"]),
    ("import yaml as y\ny.load(data, Loader=y.UnsafeLoader)", ["security.yaml"]),
    ("from yaml import load, CSafeLoader as Safe\nload(data, Safe)", []),
    ("import yaml\nyaml.safe_load(data)\nyaml.load(data, Loader=yaml.SafeLoader)", []),
    ("import yaml\nyaml.loads(data)", []),
    ("import yaml\nyaml.load(data)", ["security.yaml"]),
    ("import yaml\nyaml.unsafe_load(data, Loader=yaml.SafeLoader)", ["security.yaml"]),
    ("def f(eval):\n    return eval(data)", []),
    ("def eval(data): return data\neval(data)", []),
    ("import pickle\ndef f(pickle):\n    pickle.loads(data)", []),
    ("import pickle\n[pickle.loads(data) for pickle in parsers]\npickle.loads(data)", ["security.pickle"]),
    ("class C:\n    import pickle\n    def f(self):\n        pickle.loads(data)", []),
    ("import pickle\nclass C:\n    pickle = None\n    def f(self):\n        pickle.loads(data)", ["security.pickle"]),
    ("class Thing:\n    def loads(self, data): return data\nthing=Thing()\nthing.loads(data)", []),
    ("eval('1 + 2')\neval(data)\nexec(code)", ["security.eval", "security.exec"]),
    ("# API_KEY = '1234567890abcdef'\ntext = \"password = '1234567890abcdef'\"", []),
    ("API_KEY = 'EXAMPLE_1234567890'\nPASSWORD='aaaaaaaaaaaaaaaa'\nTOKEN='this is ordinary text'", []),
    ("API_KEY: str = '1234567890abcdef'", ["security.hardcoded-credential"]),
])
def test_security_rules_and_false_positives(tmp_path, source, rules):
    results = analyze_source(tmp_path, security, source)
    assert [f.rule_id for f in results] == rules
    for f in results:
        assert f.category == "security"
        assert f.line > 0 and f.file_path == "sample.py"
        assert f.title and f.message and f.snippet and f.fix_suggestion


def test_credentials_are_redacted_and_fixture_severity_is_lower(tmp_path):
    results = analyze_source(tmp_path, security, "API_KEY='1234567890abcdef'", "tests/test_config.py")
    assert len(results) == 1
    assert results[0].severity == "low"
    assert "1234567890abcdef" not in results[0].snippet
    assert "<redacted credential>" in results[0].snippet


def test_complexity_methods_closures_and_no_class_aggregate(tmp_path):
    source = "class Service:\n    def method(self, x):\n" + "".join(f"        if x == {n}: return {n}\n" for n in range(20))
    source += "def outer():\n    def inner(x):\n" + "".join(f"        if x == {n}: return {n}\n" for n in range(14))
    results = analyze_source(tmp_path, complexity, source)
    assert len(results) == 2
    assert {f.severity for f in results} == {"high", "medium"}
    assert any("Service.method" in f.title for f in results)
    assert any("outer.inner" in f.title for f in results)
    assert all(f.fix_suggestion and f.snippet and "Radon" in f.message for f in results)


def test_style_receiver_keyword_options_and_static_methods(tmp_path):
    source = '''
class Service:
    def valid(self, a, b, c, d, e, f, *, g=None, h=None): pass
    @classmethod
    def valid_class(cls, a, b, c, d, e, f): pass
    @staticmethod
    def long_static(a, b, c, d, e, f, g): pass
def long_function(a, b, c, d, e, f, g): pass
def named_options(*, a, b, c, d, e, f, g, h): pass
'''
    results = analyze_source(tmp_path, style, source)
    assert len(results) == 2
    assert all(f.category == "style" and f.severity == "low" and f.fix_suggestion for f in results)


def test_dead_code_omits_public_api_candidates_but_reports_unreachable(tmp_path):
    results = analyze_source(tmp_path, dead_code, "def public_api():\n    return 1\n    print('unreachable')\n")
    assert len(results) == 1
    assert results[0].category == "dead_code"
    assert results[0].severity == "medium"
    assert "100%" in results[0].message
    assert results[0].line == 3 and results[0].fix_suggestion


def test_dead_code_omits_package_reexports(tmp_path):
    assert analyze_source(tmp_path, dead_code, "from os import getenv\n", "pkg/__init__.py") == []


def test_dead_code_preserves_exact_unreachable_branch_evidence(tmp_path):
    results = analyze_source(tmp_path, dead_code, "result = 1 if False else 2\nprint(result)\n")
    assert len(results) == 1
    assert results[0].title == "Unreachable branch or statement"
    assert "surrounding statements may still run" in results[0].message
    assert "unsatisfiable 'ternary' condition" in results[0].message


def test_dead_code_multiline_import_location_and_explicit_reexports(tmp_path):
    results = analyze_source(tmp_path, dead_code, "from os import (\n    getenv,\n    getpid as getpid,\n)\n")
    assert len(results) == 1
    assert results[0].line == 2
    assert "getenv" in results[0].title


def test_dedup_is_wording_independent_stable_and_location_specific():
    a = finding("low")
    b = replace(a, severity="high", message="Reworded", title="Changed title")
    c = replace(a, column=10)
    d = replace(a, rule_id="another.rule")
    results = deduplicate_findings([a, c, b, d, a])
    assert results == deduplicate_findings([d, b, c, a])
    assert len(results) == 3 and results[0] == b
    assert a.fingerprint == b.fingerprint


def test_severity_normalization_and_rejection():
    assert finding(" HIGH ").severity == "high"
    with pytest.raises(ValueError, match="Unknown finding severity"):
        finding("severe")


@pytest.mark.parametrize("severity, expected", [("info", 99), ("low", 98), ("medium", 95), ("high", 90), ("critical", 82)])
def test_single_finding_score(severity, expected):
    assert health_score([finding(severity)]) == expected


def test_score_dedup_saturation_monotonicity_and_explanation():
    assert health_score([]) == 100
    assert health_score([finding()] * 500) == 98
    assert health_score([finding(line=n) for n in range(1, 5001)]) == 90
    scores = [health_score([finding("high", line=n) for n in range(1, count + 1)]) for count in range(1, 40)]
    assert scores == sorted(scores, reverse=True)
    base = [finding("low", line=n) for n in range(1, 100)]
    assert health_score(base + [finding("critical", line=101)]) < health_score(base)
    breakdown = health_score_breakdown(base)
    assert breakdown["version"] == "2" and breakdown["counts"] == {"low": 99}
    assert 0 <= breakdown["score"] <= 100


def test_upgrading_severity_never_improves_score_even_with_saturated_buckets():
    severities = ["info", "low", "medium", "high", "critical"]
    for saturated in severities:
        base = [finding(saturated, line=n) for n in range(1, 200)]
        scores = [health_score(base + [finding(severity, line=201)]) for severity in severities]
        assert scores == sorted(scores, reverse=True)


def install_ai(monkeypatch, parse, constructor_error=False):
    monkeypatch.setattr(reasoner, "get_settings", lambda: SimpleNamespace(anthropic_api_key="test", anthropic_model="test"))
    client = SimpleNamespace(messages=SimpleNamespace(parse=parse), close=lambda: None)
    def constructor(**kwargs):
        assert kwargs["timeout"] == 15 and kwargs["max_retries"] == 0
        if constructor_error:
            raise RuntimeError("unavailable")
        return client
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=constructor))


def review(fp, **kwargs):
    return reasoner.Review(fingerprint=fp, severity="critical", confidence=0.9, is_false_positive=False,
                          explanation="Context-dependent impact", fix_suggestion="Practical fix", **kwargs)


def test_ai_disabled_constructor_failure_and_request_failure(monkeypatch):
    monkeypatch.setattr(reasoner, "get_settings", lambda: SimpleNamespace(anthropic_api_key=""))
    assert reasoner.review_findings([finding()]) == {}
    install_ai(monkeypatch, lambda **_: None, constructor_error=True)
    assert reasoner.review_findings([finding()]) == {}
    def fail(**kwargs):
        raise TimeoutError("simulated")
    install_ai(monkeypatch, fail)
    assert reasoner.review_findings([finding()]) == {}


def test_ai_accepts_only_known_confident_reviews_and_keeps_analyzer_immutable(monkeypatch):
    f = finding()
    valid = review(f.fingerprint)
    other = finding(line=2)
    low_confidence = review(other.fingerprint).model_copy(update={"confidence": 0.3})
    install_ai(monkeypatch, lambda **_: SimpleNamespace(parsed_output=reasoner.ReviewBatch(
        reviews=[review("invented"), valid, valid, low_confidence])))
    assert reasoner.review_findings([f, other]) == {f.fingerprint: valid}
    assert f.severity == "low" and health_score([f]) == 98


@pytest.mark.parametrize("batch_size, expected", [(8, 24), (1, 3)])
def test_ai_limits_requests_and_prioritizes_severity(monkeypatch, batch_size, expected):
    batches = []
    def parse(**kwargs):
        batches.append(json.loads(kwargs["messages"][0]["content"].split('\n', 1)[1]))
        return SimpleNamespace(parsed_output=None)
    install_ai(monkeypatch, parse)
    reasoner.review_findings([finding(line=n) for n in range(1, 40)] + [finding("critical", line=99)], batch_size=batch_size)
    assert len(batches) == 3 and sum(map(len, batches)) == expected
    assert batches[0][0]["analyzer_severity"] == "critical"


def test_ai_invalid_text_rejected_and_soft_limit_propagates(monkeypatch):
    with pytest.raises(ValidationError):
        reasoner.Review(fingerprint="x", severity="high", confidence=0.9, is_false_positive=False,
                        explanation="   ", fix_suggestion="fix")
    def stop(**kwargs):
        raise SoftTimeLimitExceeded()
    install_ai(monkeypatch, stop)
    with pytest.raises(SoftTimeLimitExceeded):
        reasoner.review_findings([finding()])


def test_inventory_safeguards_remain_in_force(tmp_path, monkeypatch):
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'skip.py').write_text('eval(x)')
    (tmp_path / 'a.py').write_text('x=1')
    (tmp_path / 'b.py').write_text('y=2')
    (tmp_path / 'large.py').write_text('x' * 100)
    monkeypatch.setattr(common, 'MAX_FILE_BYTES', 50)
    assert [p.name for p in common.iter_python_files(tmp_path)] == ['a.py', 'b.py']
    monkeypatch.setattr(common, 'MAX_PYTHON_FILES', 1)
    assert [p.name for p in common.iter_python_files(tmp_path)] == ['a.py']
