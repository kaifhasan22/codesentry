from app.services.progress import estimate_ai_remaining, estimate_static_remaining


def test_static_estimate_scales_with_repository_workload():
    small = estimate_static_remaining(file_count=10, source_bytes=100_000, ai_enabled=False)
    large = estimate_static_remaining(file_count=1_000, source_bytes=10_000_000, ai_enabled=False)

    assert small[0] < small[1]
    assert large[0] < large[1]
    assert large[0] > small[0]
    assert large[1] > small[1]


def test_ai_estimate_is_bounded_by_review_cap_and_configuration():
    no_ai = estimate_ai_remaining(findings_count=200, ai_enabled=False)
    capped = estimate_ai_remaining(findings_count=200, ai_enabled=True)
    at_cap = estimate_ai_remaining(findings_count=24, ai_enabled=True)

    assert no_ai == (2, 10)
    assert capped == at_cap
    assert capped[0] < capped[1]
