"""
Evaluation Runner for AI-Medibot

Runs a list of evaluation prompts against the live backend API:
- POST /api/v1/chat
- GET  /api/v1/chat/{chat_message_id}/explain
- GET  /api/v1/chat/{chat_message_id}/explain-rag

Outputs:
- JSON report saved under backend/app/scripts/reports/
- eval_report_latest.json overwritten each run
"""

from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


# =========================
# Config
# =========================

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CHAT_ENDPOINT = "/api/v1/chat"
DEFAULT_CASES_FILE = "eval_cases.json"


@dataclass
class EvalCase:
    name: str
    message: str
    category: str = "general"

    # expectations
    expected_risk_level: Optional[str] = None          # "green" | "yellow" | "red"
    expected_emergency_detected: Optional[bool] = None
    expected_primary_domain: Optional[str] = None      # e.g. "cardiology", "general"
    require_citations: Optional[bool] = None           # True/False/None
    min_retrieved_chunks: Optional[int] = None         # e.g. 1, 2, 3


@dataclass
class EvalResult:
    case: Dict[str, Any]
    ok: bool
    failures: List[str]

    conversation_id: Optional[int] = None
    chat_message_id: Optional[int] = None

    chat_reply: Optional[str] = None
    citations_count: int = 0

    explain: Optional[Dict[str, Any]] = None
    explain_rag: Optional[Dict[str, Any]] = None


# =========================
# Helpers
# =========================

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _safe_get(d: Dict[str, Any], key: str, default=None):
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def _http_headers(token: str) -> Dict[str, str]:
    return {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def _request_json(method: str, url: str, headers: Dict[str, str], payload: Optional[dict] = None) -> Dict[str, Any]:
    try:
        if method.upper() == "POST":
            r = requests.post(url, headers=headers, json=payload, timeout=60)
        else:
            r = requests.get(url, headers=headers, timeout=60)

        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error {r.status_code} for {url}: {r.text}") from e
    except Exception as e:
        raise RuntimeError(f"Request failed for {url}: {str(e)}") from e


def load_cases_from_json(path: Path) -> List[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(
            f"Cases file not found: {path}\n"
            f"Create it like: {path.parent / DEFAULT_CASES_FILE}"
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = data.get("cases", [])

    cases: List[EvalCase] = []
    for c in raw_cases:
        cases.append(
            EvalCase(
                name=c["name"],
                message=c["message"],
                category=c.get("category", "general"),
                expected_risk_level=c.get("expected_risk_level"),
                expected_emergency_detected=c.get("expected_emergency_detected"),
                expected_primary_domain=c.get("expected_primary_domain"),
                require_citations=c.get("require_citations"),
                min_retrieved_chunks=c.get("min_retrieved_chunks"),
            )
        )
    return cases


def _check_expectations(
    case: EvalCase,
    chat_json: Dict[str, Any],
    explain_json: Optional[Dict[str, Any]],
    explain_rag_json: Optional[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    failures: List[str] = []

    citations = _safe_get(chat_json, "citations", []) or []
    citations_count = len(citations) if isinstance(citations, list) else 0

    # explain checks
    risk_level = _safe_get(explain_json or {}, "risk_level")
    emergency_detected = _safe_get(explain_json or {}, "emergency_detected")
    primary_domain = _safe_get(explain_json or {}, "primary_domain")

    # explain-rag checks
    rag_block = _safe_get(explain_rag_json or {}, "rag", {}) or {}
    citations_returned = _safe_get(rag_block, "citations_returned")
    retrieved_chunks = _safe_get(rag_block, "retrieved_chunks", []) or []
    retrieved_count = len(retrieved_chunks) if isinstance(retrieved_chunks, list) else 0
    suppression_reason = _safe_get(rag_block, "suppression_reason")

    # basic expectations
    if case.expected_risk_level is not None and risk_level != case.expected_risk_level:
        failures.append(f"expected risk_level='{case.expected_risk_level}', got '{risk_level}'")

    if case.expected_emergency_detected is not None and emergency_detected != case.expected_emergency_detected:
        failures.append(f"expected emergency_detected={case.expected_emergency_detected}, got {emergency_detected}")

    if case.expected_primary_domain is not None and primary_domain != case.expected_primary_domain:
        failures.append(f"expected primary_domain='{case.expected_primary_domain}', got '{primary_domain}'")

    # citation expectations
    if case.require_citations is True:
        if citations_count == 0 and citations_returned is not True:
            failures.append("expected citations, but none returned in chat and explain-rag")

    if case.require_citations is False:
        if citations_count > 0:
            failures.append(f"expected NO citations, but chat returned {citations_count}")

    # RAG retrieval expectations
    if case.min_retrieved_chunks is not None:
        if retrieved_count < case.min_retrieved_chunks:
            failures.append(f"expected at least {case.min_retrieved_chunks} retrieved_chunks, got {retrieved_count}")

    # policy checks (stronger)
    # If emergency detected, citations should be suppressed
    if emergency_detected is True and citations_count > 0:
        failures.append("emergency_detected=True but citations were returned in chat (should be suppressed)")

    # If citations are suppressed, suppression_reason should exist (debuggability)
    if citations_count == 0 and case.require_citations is False:
        # allow either None or a reason; but better if present
        if suppression_reason is None:
            # not a hard fail, but useful signal
            pass

    return (len(failures) == 0), failures


# =========================
# Runner
# =========================

def run_eval_cases(
    cases: List[EvalCase],
    base_url: str,
    token: str,
    sleep_s: float = 0.1,
) -> List[EvalResult]:
    headers = _http_headers(token)
    results: List[EvalResult] = []

    chat_url = base_url.rstrip("/") + DEFAULT_CHAT_ENDPOINT

    for idx, case in enumerate(cases, start=1):
        print(f"\n[{idx}/{len(cases)}] ({case.category}) {case.name}")
        print(f"Prompt: {case.message}")

        # 1) chat
        chat_json = _request_json(
            "POST",
            chat_url,
            headers=headers,
            payload={"message": case.message},
        )

        conversation_id = _safe_get(chat_json, "conversation_id")
        chat_message_id = _safe_get(chat_json, "chat_message_id")

        reply = _safe_get(chat_json, "reply")
        citations = _safe_get(chat_json, "citations", []) or []
        citations_count = len(citations) if isinstance(citations, list) else 0

        # 2) explain + explain-rag
        explain_json = None
        explain_rag_json = None

        if chat_message_id is None:
            explain_json = {"error": "chat_message_id not returned by /chat"}
            explain_rag_json = {"error": "chat_message_id not returned by /chat"}
        else:
            explain_url = f"{base_url.rstrip('/')}/api/v1/chat/{chat_message_id}/explain"
            explain_rag_url = f"{base_url.rstrip('/')}/api/v1/chat/{chat_message_id}/explain-rag"

            explain_json = _request_json("GET", explain_url, headers=headers)
            explain_rag_json = _request_json("GET", explain_rag_url, headers=headers)

        ok, failures = _check_expectations(case, chat_json, explain_json, explain_rag_json)

        results.append(
            EvalResult(
                case=asdict(case),
                ok=ok,
                failures=failures,
                conversation_id=conversation_id,
                chat_message_id=chat_message_id,
                chat_reply=reply,
                citations_count=citations_count,
                explain=explain_json,
                explain_rag=explain_rag_json,
            )
        )

        if ok:
            print("✅ PASS")
        else:
            print("❌ FAIL")
            for f in failures:
                print("   -", f)

        time.sleep(sleep_s)

    return results


def save_report(results: List[EvalResult]) -> str:
    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"eval_report_{ts}.json"
    latest_path = out_dir / "eval_report_latest.json"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(results),
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "by_category": {},
        "results": [asdict(r) for r in results],
    }

    # category summary
    cat_stats: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = (r.case or {}).get("category", "general")
        cat_stats.setdefault(cat, {"passed": 0, "failed": 0})
        if r.ok:
            cat_stats[cat]["passed"] += 1
        else:
            cat_stats[cat]["failed"] += 1

    payload["by_category"] = cat_stats

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return str(out_path)


def main():
    base_url = _env("EVAL_BASE_URL", DEFAULT_BASE_URL)
    token = _env("EVAL_TOKEN")

    if not token:
        print("\n❌ Missing EVAL_TOKEN.")
        print("Set it like:")
        print('  Windows PowerShell:  $env:EVAL_TOKEN="YOUR_JWT"')
        print('  Git Bash:            export EVAL_TOKEN="YOUR_JWT"')
        return

    cases_file = _env("EVAL_CASES_FILE", DEFAULT_CASES_FILE)
    cases_path = Path(__file__).parent / cases_file

    cases = load_cases_from_json(cases_path)

    print("\n==============================")
    print("AI-Medibot Evaluation Runner")
    print("==============================")
    print("Base URL:", base_url)
    print("Cases:", str(cases_path))

    results = run_eval_cases(cases, base_url=base_url, token=token)

    report_path = save_report(results)

    print("\n==============================")
    print("Summary")
    print("==============================")
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    failed = total - passed
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")

    # category summary
    cat_summary: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = (r.case or {}).get("category", "general")
        cat_summary.setdefault(cat, {"passed": 0, "failed": 0})
        if r.ok:
            cat_summary[cat]["passed"] += 1
        else:
            cat_summary[cat]["failed"] += 1

    print("\nBy category:")
    for cat, st in cat_summary.items():
        print(f"  - {cat}: {st['passed']} passed, {st['failed']} failed")

    print("\nReport saved to:", report_path)
    print("Latest report:", str((Path(__file__).parent / 'reports' / 'eval_report_latest.json')))

    if failed > 0:
        print("\n❗ Some cases failed. Open the JSON report for details.")


if __name__ == "__main__":
    main()

