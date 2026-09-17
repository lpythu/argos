import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models import CaseRow, Run

_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
_HEX_RE = re.compile(r"\b[0-9a-f]{12,}\b", re.I)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_STAMP_RE = re.compile(r"\b20\d{2}[-/]?\d{2}[-/]?\d{2}[T _-]?\d{2}:?\d{2}:?\d{2}(?:\.\d+)?Z?\b")

LIVE = frozenset({"running", "paused"})


def _run_id(run: "Run") -> str:
    return run.sid or str(run.id)


def fingerprint(message: str) -> tuple[str, str]:
    display = " ".join(str(message or "").split())
    normalized = _UUID_RE.sub("<id>", display)
    normalized = _HEX_RE.sub("<id>", normalized)
    normalized = _IP_RE.sub("<ip>", normalized)
    normalized = _STAMP_RE.sub("<time>", normalized)
    normalized = normalized[:240] or "unrecorded failure"
    key = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    return key, normalized


def is_cleanup(error: str) -> bool:
    text = error or ""
    return "清理" in text or "cleanup" in text.lower() or "删除后仍存在" in text


def counts(run: "Run") -> dict[str, int]:
    summary = run.summary if isinstance(run.summary, dict) else {}
    if any(key in summary for key in ("passed", "failed", "skipped")):
        return {
            "passed": int(summary.get("passed") or 0),
            "failed": int(summary.get("failed") or 0),
            "skipped": int(summary.get("skipped") or 0),
            "interrupted": int(summary.get("interrupted") or 0),
        }
    out = {"passed": 0, "failed": 0, "skipped": 0, "interrupted": 0}
    for row in run.cases:
        if row.status in out:
            out[row.status] += 1
    return out


def elapsed_s(run: "Run") -> float:
    summary = run.summary if isinstance(run.summary, dict) else {}
    if summary.get("elapsed_s") is not None:
        return float(summary.get("elapsed_s") or 0)
    return round(sum(row.elapsed_s for row in run.cases), 3)


def current_task(run: "Run") -> dict[str, Any]:
    live = [row for row in run.cases if row.status == "running"]
    row = live[-1] if live else (run.cases[-1] if run.cases else None)
    if row is None:
        return {}
    step = ""
    for item in row.steps or []:
        if isinstance(item, dict) and item.get("status") in {"running", "start"}:
            step = str(item.get("name") or "")
            break
    if not step and row.steps:
        last = row.steps[-1]
        if isinstance(last, dict):
            step = str(last.get("name") or "")
    return {
        "case_id": row.spec_id,
        "status": row.status,
        "iteration": row.iteration,
        "step": step,
    }


def load_report(root: Path) -> dict[str, Any]:
    path = root / "report.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def list_files(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in {"events.jsonl", "run.json"}:
            continue
        rows.append({"path": rel, "size": path.stat().st_size})
    return rows


def _metric_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def detail(run: "Run", root: Path) -> dict[str, Any]:
    report = load_report(root)
    extra: dict[tuple[str, int], dict[str, Any]] = {}
    for item in report.get("cases") or []:
        if not isinstance(item, dict):
            continue
        extra[(str(item.get("id") or ""), int(item.get("iteration") or 0))] = item

    grouped: dict[str, list["CaseRow"]] = defaultdict(list)
    for row in sorted(run.cases, key=lambda item: (item.spec_id, item.iteration)):
        grouped[row.spec_id].append(row)

    summaries: list[dict[str, Any]] = []
    series: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for spec_id, rows in grouped.items():
        tallies = {"passed": 0, "failed": 0, "skipped": 0, "interrupted": 0, "running": 0}
        iterations: list[dict[str, Any]] = []
        keys: dict[str, list[dict[str, Any]]] = defaultdict(list)
        last = rows[-1]
        last_extra = extra.get((spec_id, last.iteration), {})
        for row in rows:
            if row.status in tallies:
                tallies[row.status] += 1
            iterations.append({"iteration": row.iteration, "status": row.status})
            payload = extra.get((spec_id, row.iteration), {})
            metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else row.metrics
            for key, value in (metrics or {}).items():
                number = _metric_number(value)
                if number is None:
                    continue
                keys[str(key)].append({"iter": row.iteration, "value": number})
        finished = tallies["passed"] + tallies["failed"]
        summaries.append(
            {
                "id": spec_id,
                "title": last.title,
                "pack": last.pack,
                "group": last.group,
                "latest_status": last.status,
                "latest_error": last.error,
                "elapsed_s": round(sum(row.elapsed_s for row in rows), 3),
                "total": len(rows),
                "passed": tallies["passed"],
                "failed": tallies["failed"],
                "skipped": tallies["skipped"],
                "interrupted": tallies["interrupted"],
                "running": tallies["running"],
                "success_rate": round(100 * tallies["passed"] / finished, 1) if finished else None,
                "iterations": iterations,
                "metrics": last_extra.get("metrics") or last.metrics,
                "metric_meta": last_extra.get("metric_meta") or {},
                "distributions": last_extra.get("distributions") or {},
                "thresholds": last_extra.get("thresholds") or [],
                "steps": last_extra.get("steps") or last.steps,
            }
        )
        if keys:
            series[spec_id] = dict(keys)

    issues: dict[str, dict[str, Any]] = {}
    for row in run.cases:
        if row.status != "fail":
            continue
        key, message = fingerprint(row.error)
        issue = issues.setdefault(
            key,
            {"fingerprint": key, "message": message, "count": 0, "cases": set(), "iterations": set()},
        )
        issue["count"] += 1
        issue["cases"].add(row.spec_id)
        issue["iterations"].add(row.iteration)
    issue_rows = [
        {
            "fingerprint": item["fingerprint"],
            "message": item["message"],
            "count": item["count"],
            "cases": sorted(item["cases"]),
            "iterations": sorted(item["iterations"]),
        }
        for item in issues.values()
    ]
    issue_rows.sort(key=lambda item: (-item["count"], item["message"]))

    audit = dict(report.get("resource_audit") or {}) if isinstance(report.get("resource_audit"), dict) else {}
    cleanup = report.get("cleanup") if isinstance(report.get("cleanup"), dict) else {}
    if cleanup:
        audit["cleanup_completed"] = cleanup.get("completed")
        audit["cleanup_failed"] = cleanup.get("failed")
        audit["cleanup_status"] = cleanup.get("status")
    files = list_files(root)
    stats = counts(run)
    return {
        **stats,
        "elapsed_s": elapsed_s(run),
        "case_summaries": summaries,
        "metric_series": series,
        "issues": issue_rows,
        "resource_audit": audit,
        "has_report": (root / "report.html").is_file() or (root / "report.json").is_file(),
        "files": files,
    }


def catalog(runs: list["Run"]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in sorted(runs, key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC)):
        extras: dict[str, dict[str, Any]] = {}
        summary = run.summary if isinstance(run.summary, dict) else {}
        for item in summary.get("cases") or []:
            if isinstance(item, dict) and item.get("id"):
                extras[str(item["id"])] = item
        for row in run.cases:
            if not row.spec_id:
                continue
            extra = extras.get(row.spec_id, {})
            latest[row.spec_id] = {
                "id": row.spec_id,
                "title": row.title,
                "pack": row.pack,
                "group": row.group,
                "slug": row.slug,
                "status": row.status,
                "env": run.env,
                "mode": run.mode,
                "run_id": _run_id(run),
                "run_slug": run.slug,
                "seen_at": run.created_at.isoformat() if run.created_at else "",
                "typical_s": int(extra.get("typical_s") or 0),
                "mutex": str(extra.get("mutex") or ""),
                "resources": list(extra.get("resources") or []),
                "prefer_after": list(extra.get("prefer_after") or []),
                "modes": list(extra.get("modes") or []),
                "tags": list(extra.get("tags") or []),
            }
    return sorted(latest.values(), key=lambda item: item["id"])


def overview(runs: list["Run"], *, hours: int, env: str, catalog_ids: set[str]) -> dict[str, Any]:
    ordered = sorted(runs, key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC))
    totals = {"runs": len(ordered), "passed": 0, "failed": 0, "skipped": 0, "interrupted": 0}
    coverage: set[str] = set()
    issue_groups: dict[str, dict[str, Any]] = {}
    latest_by_case: dict[str, tuple[str, str]] = {}
    streaks: dict[str, tuple[str, int]] = {}
    cleanup_failures = 0
    live: list["Run"] = []

    for run in ordered:
        stats = counts(run)
        for key in ("passed", "failed", "skipped", "interrupted"):
            totals[key] += stats[key]
        if run.status in LIVE:
            live.append(run)
        for row in sorted(run.cases, key=lambda item: item.iteration):
            if not row.spec_id:
                continue
            coverage.add(row.spec_id)
            if row.status != "fail":
                streaks[row.spec_id] = ("", 0)
                latest_by_case[row.spec_id] = (row.status, "")
                continue
            key, message = fingerprint(row.error)
            previous_key, previous_count = streaks.get(row.spec_id, ("", 0))
            streaks[row.spec_id] = (key, previous_count + 1 if previous_key == key else 1)
            latest_by_case[row.spec_id] = ("fail", key)
            if is_cleanup(row.error):
                cleanup_failures += 1
            stamp = run.created_at.isoformat() if run.created_at else ""
            issue = issue_groups.setdefault(
                key,
                {
                    "fingerprint": key,
                    "message": message,
                    "count": 0,
                    "cases": set(),
                    "envs": set(),
                    "first": stamp,
                    "last": stamp,
                    "latest_run": _run_id(run),
                    "latest_slug": run.sid or run.slug or run.stamp,
                },
            )
            issue["count"] += 1
            issue["cases"].add(row.spec_id)
            issue["envs"].add(run.env or "-")
            issue["last"] = stamp
            issue["latest_run"] = _run_id(run)
            issue["latest_slug"] = run.sid or run.slug or run.stamp

    issues: list[dict[str, Any]] = []
    for issue in issue_groups.values():
        open_cases = [
            case_id
            for case_id in issue["cases"]
            if latest_by_case.get(case_id) == ("fail", issue["fingerprint"])
        ]
        issue["open"] = bool(open_cases)
        issue["cases"] = sorted(issue["cases"])
        issue["envs"] = sorted(issue["envs"])
        issue["max_streak"] = max(
            (
                count
                for case_id in open_cases
                for fingerprint_key, count in [streaks.get(case_id, ("", 0))]
                if fingerprint_key == issue["fingerprint"]
            ),
            default=0,
        )
        issues.append(issue)
    issues.sort(key=lambda item: (not item["open"], -int(item["max_streak"]), str(item["last"])))

    completed = totals["passed"] + totals["failed"]
    totals["success_rate"] = round(100 * totals["passed"] / completed, 1) if completed else None
    eligible = {item for item in catalog_ids if item} or coverage
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hours": hours,
        "env": env,
        "totals": totals,
        "coverage": sorted(coverage),
        "coverage_total": len(eligible),
        "open_issues": sum(1 for issue in issues if issue["open"]),
        "consecutive_failure_cases": sum(1 for _, count in streaks.values() if count >= 2),
        "cleanup_failures": cleanup_failures,
        "issues": issues,
        "live": [
            {
                "id": _run_id(run),
                "sid": _run_id(run),
                "slug": run.slug or run.stamp,
                "source": dict(run.source) if isinstance(run.source, dict) else {},
                "env": run.env,
                "mode": run.mode,
                "status": run.status,
                "runner": run.runner,
                "created_at": run.created_at.isoformat() if run.created_at else "",
                **counts(run),
                "current": current_task(run),
            }
            for run in live
        ],
    }
