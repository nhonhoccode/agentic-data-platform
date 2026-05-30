"""Unit tests for domain_filter._parse_verdict — the part most prone to break
when an LLM returns markdown / quoted / JSON-wrapped verdicts."""

from __future__ import annotations

import pytest

from app.agent.domain_filter import _parse_verdict


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("VERDICT: YES", True),
        ("VERDICT: NO", False),
        ("**VERDICT:** YES", True),  # markdown bold
        ("verdict: yes\nREASON: ok", True),  # lowercase + extra
        ('"YES"', True),  # quoted bare token
        ("```json\n{\"verdict\":\"yes\"}\n```", True),  # JSON in fence
        ("```\nVERDICT: NO\n```", False),
        ("Verdict: out_of_domain", False),
        ("nothing here", None),  # unparseable -> None (fallback)
        ("", None),
        ("YES", True),
        ("no", False),
    ],
)
def test_parse_verdict(raw: str, expected: bool | None) -> None:
    assert _parse_verdict(raw) is expected


def test_keyword_verdict_positive() -> None:
    from app.agent.domain_keywords import keyword_verdict

    assert keyword_verdict("doanh thu Olist tháng 5") is True
    assert keyword_verdict("GMV tăng trưởng") is True
    assert keyword_verdict("dbt incremental model") is True


def test_keyword_verdict_negative() -> None:
    from app.agent.domain_keywords import keyword_verdict

    assert keyword_verdict("thời tiết Hà Nội") is False
    assert keyword_verdict("bài hát mới Sơn Tùng") is False


def test_keyword_verdict_ambiguous() -> None:
    from app.agent.domain_keywords import keyword_verdict

    assert keyword_verdict("xin chào") is None
    assert keyword_verdict("") is None
