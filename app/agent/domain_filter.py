"""LLM-backed in-domain classifier with keyword fallback.

The Olist AI Data Platform deliberately scopes web search to ecommerce /
data engineering topics so the limited Tavily quota is not spent on
weather, music, gossip, etc. `classify_in_domain(question)` returns a
verdict tuple (in_domain, reason).

Decision order:
1. Ask the LLM via `llm_invoke_text`. Parse JSON / **VERDICT:** YES / bare
   "yes" / "no" answers.
2. On exception or ambiguous parse, fall back to keyword heuristics.
3. If everything is ambiguous AND LLM unavailable → return
   (False, "fail-closed") so we don't burn web-search quota on a wild guess.
"""

from __future__ import annotations

import json
import re

from app.agent.domain_keywords import keyword_verdict


_DOMAIN_PROMPT = """Bạn là bộ lọc domain cho một trợ lý phân tích dữ liệu thương mại điện tử (ecommerce / data engineering).
Nhiệm vụ: quyết định câu hỏi có thuộc domain hay không.

TRONG DOMAIN (YES) bao gồm:
- KPI / metric ecommerce: GMV, AOV, conversion rate, retention, LTV, churn...
- Catalog, seller, buyer, fulfillment, logistics, marketplace.
- Data engineering: SQL, dbt, warehouse, BigQuery, Snowflake, Airflow, ETL/ELT.
- Tin tức / xu hướng ecommerce hoặc data ở Brazil / Đông Nam Á (Shopee, Lazada, Tiki, Olist...).

NGOÀI DOMAIN (NO) bao gồm:
- Thời tiết, ca nhạc, bóng đá, phim ảnh, game, tử vi, người nổi tiếng, tin lá cải.

QUY TẮC TIE-BREAK: khi không chắc chắn → trả YES (ưu tiên hỗ trợ người dùng).

Ví dụ:
Q: "GMV của Shopee tháng trước?"  → VERDICT: YES
Q: "Sơn Tùng MTP có album mới không?"  → VERDICT: NO
Q: "dbt incremental model best practice"  → VERDICT: YES
Q: "Thời tiết Hà Nội hôm nay"  → VERDICT: NO
Q: "phân tích doanh thu Q3"  → VERDICT: YES

Câu hỏi: {question}

Chỉ trả về 1 dòng đúng định dạng:
VERDICT: YES
hoặc
VERDICT: NO
"""

_VERDICT_RE = re.compile(r"verdict\s*:?\s*\**\s*([A-Za-z]+)", re.IGNORECASE)


def _parse_verdict(raw: str | None) -> bool | None:
    """Robust parser. Handles:
    - JSON like {"verdict": "yes"}
    - "**VERDICT:** YES"
    - "verdict: no"
    - bare tokens "yes"/"no"/"true"/"false"/"in"/"out"
    Returns True / False / None (unparseable).
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None

    # Strip ```json ... ``` or ``` ... ``` fences (LLMs love wrapping in fences)
    fence_match = re.match(r"^```(?:json|JSON)?\s*\n?(.*?)\n?\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    if not text:
        return None

    # JSON path
    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
            for key in ("verdict", "answer", "in_domain"):
                if key in obj:
                    val = obj[key]
                    if isinstance(val, bool):
                        return val
                    if isinstance(val, str):
                        return _parse_verdict(val)
        except (json.JSONDecodeError, TypeError):
            pass

    # Regex search for "verdict: <token>" — handles markdown bold etc.
    m = _VERDICT_RE.search(text)
    candidate = m.group(1) if m else text

    cleaned = candidate.strip().strip("\"'`*.").lower()
    if cleaned in {"yes", "y", "true", "1", "in", "in_domain", "in-domain", "domain"}:
        return True
    if cleaned in {"no", "n", "false", "0", "out", "out_of_domain", "out-of-domain", "off"}:
        return False
    return None


def classify_in_domain(question: str) -> tuple[bool, str]:
    """Return (in_domain, reason).

    reason is one of:
      - "llm:yes" / "llm:no"      — LLM gave a confident verdict
      - "keyword:positive" / "keyword:negative" — fell back to keywords
      - "fail-closed"             — totally ambiguous + LLM unavailable
      - "cache:<reason>"          — value pulled from 24h TTL cache
    """
    q = (question or "").strip()
    if not q:
        return False, "fail-closed"

    # Cache hit short-circuit — saves one LLM call per repeated query.
    try:
        from app.agent.cache import get as cache_get

        cached = cache_get("domain", q)
        if isinstance(cached, dict) and "in_domain" in cached and "reason" in cached:
            return bool(cached["in_domain"]), f"cache:{cached['reason']}"
    except Exception:  # noqa: BLE001
        pass

    llm_verdict: bool | None = None
    try:
        from app.agent.llm import llm_invoke_text

        prompt = _DOMAIN_PROMPT.format(question=q[:500])
        raw = llm_invoke_text(prompt)
        llm_verdict = _parse_verdict(raw)
    except Exception:  # noqa: BLE001
        llm_verdict = None

    def _persist(value: bool, reason: str) -> tuple[bool, str]:
        try:
            from app.agent.cache import set as cache_set

            cache_set("domain", q, {"in_domain": value, "reason": reason}, ttl_sec=86400)
        except Exception:  # noqa: BLE001
            pass
        return value, reason

    if llm_verdict is True:
        return _persist(True, "llm:yes")
    if llm_verdict is False:
        return _persist(False, "llm:no")

    kw = keyword_verdict(q)
    if kw is True:
        return _persist(True, "keyword:positive")
    if kw is False:
        return _persist(False, "keyword:negative")

    # Fully ambiguous + LLM unavailable → save quota. Don't cache "fail-closed"
    # so a recovered LLM can produce a real answer next round.
    return False, "fail-closed"
