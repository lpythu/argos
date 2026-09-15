"""Structured common report renderer used by every Argos case."""

import copy
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path

from argos.case import Result
from argos.term import fmt_dur

_STATIC_REPORT = Path(__file__).resolve().parent / "static" / "report"
_ITER_DIR = re.compile(r"^(.+)__(\d{4})$")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
_HEX_RE = re.compile(r"\b[0-9a-f]{12,}\b", re.I)
_ARGOS_NAME_RE = re.compile(r"\bargos-[a-z0-9-]*-[0-9a-f]{8}\b", re.I)
_SENSITIVE_NAMES = ("凭据", "credential", "password", "token", "secret")


def _read_json(path: Path) -> dict | list | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) else None


def _result_payload(result: Result) -> dict:
    from argos.suite import plan_meta

    meta = plan_meta(result.spec)
    return {
        "id": result.spec.id, "slug": result.spec.slug, "iteration": result.iteration,
        "title": result.spec.title, "group": result.spec.group, "pack": result.spec.pack,
        "tags": list(result.spec.tags), "modes": list(result.spec.modes),
        "status": result.status, "elapsed_s": round(result.elapsed_s, 3), "error": result.error,
        "metrics": result.metrics, "steps": [step.__dict__ for step in result.steps],
        "metric_meta": result.metric_meta, "samples": result.samples,
        "distributions": result.distributions, "thresholds": result.thresholds,
        "notes": result.notes, "dest": result.dest,
        "typical_s": int(meta.get("typical_s") or 0),
        "mutex": str(meta.get("mutex") or ""),
        "resources": list(meta.get("resources") or []),
        "prefer_after": list(meta.get("prefer_after") or []),
    }


def _incomplete_results(dest: Path, existing: list[dict]) -> list[dict]:
    known = {(str(row.get("slug") or ""), int(row.get("iteration") or 0)) for row in existing}
    rows = []
    for child in sorted(dest.iterdir()):
        if not child.is_dir() or child.name == "soak-teardown" or (child / "result.json").is_file():
            continue
        progress = _read_json(child / "progress.json")
        if not isinstance(progress, dict):
            continue
        match = _ITER_DIR.match(child.name)
        slug = match.group(1) if match else str(progress.get("slug") or child.name)
        iteration = int(match.group(2)) if match else 0
        if (slug, iteration) in known:
            continue
        steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
        elapsed = sum(float(step.get("elapsed_s") or 0) for step in steps if isinstance(step, dict))
        rows.append({
            "id": progress.get("id") or slug, "slug": slug, "iteration": iteration,
            "title": progress.get("title") or "", "group": "", "pack": "",
            "tags": [], "modes": [], "status": "interrupted", "elapsed_s": round(elapsed, 3),
            "error": "本轮未生成最终结果，执行可能被停止或中断",
            "metrics": progress.get("metrics") if isinstance(progress.get("metrics"), dict) else {},
            "metric_meta": progress.get("metric_meta") if isinstance(progress.get("metric_meta"), dict) else {},
            "samples": progress.get("samples") if isinstance(progress.get("samples"), dict) else {},
            "distributions": progress.get("distributions") if isinstance(progress.get("distributions"), dict) else {},
            "thresholds": progress.get("thresholds") if isinstance(progress.get("thresholds"), list) else [],
            "steps": steps,
            "notes": progress.get("notes") if isinstance(progress.get("notes"), list) else [],
            "dest": str(child),
        })
    return rows


def _artifacts(dest: Path) -> list[dict]:
    rows = []
    for path in sorted(dest.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dest).as_posix()
        lowered = rel.lower()
        if rel in {"report.html", "report.json", "report.md", "run.json", "events.jsonl", "owned.json"}:
            continue
        if path.name in {"case.json", "progress.json", "result.json"}:
            continue
        if any(word in lowered for word in _SENSITIVE_NAMES):
            continue
        rows.append({"path": rel, "bytes": path.stat().st_size})
    return rows


def _cleanup_summary(cases: list[dict], dest: Path | None) -> dict:
    steps = []
    for case in cases:
        for step in case.get("steps") or []:
            name = str(step.get("name") or "")
            if "清理" in name or name.startswith("删除"):
                steps.append({"case": case.get("id") or "", **step})
    if dest:
        teardown = _read_json(dest / "soak-teardown" / "progress.json")
        if isinstance(teardown, dict):
            steps.extend({"case": "soak-teardown", **step} for step in teardown.get("steps") or [] if isinstance(step, dict))
    failed = sum(str(step.get("status")) == "failed" for step in steps)
    completed = sum(str(step.get("status")) == "ok" for step in steps)
    return {"status": "fail" if failed else "pass" if steps else "unknown", "completed": completed, "failed": failed, "steps": steps}


def enrich_payload(payload: dict, dest: Path | None = None) -> dict:
    """Add run metadata, cleanup, artifacts and visible unfinished iterations."""
    data = copy.deepcopy(payload)
    cases = [row for row in (data.get("cases") or []) if isinstance(row, dict)]
    run = {}
    if dest:
        raw = _read_json(dest / "run.json")
        run = raw if isinstance(raw, dict) else {}
        cases.extend(_incomplete_results(dest, cases))
    cases.sort(key=lambda row: (str(row.get("id") or ""), int(row.get("iteration") or 0)))
    data["cases"] = cases
    data["started"] = data.get("started") or run.get("started") or ""
    for key in ("env", "mode", "duration", "pause", "fail_fast", "queries", "packs"):
        if data.get(key) in (None, "", []):
            data[key] = run.get(key)
    if dest:
        report_path = dest / "report.json"
        modified = report_path.stat().st_mtime if report_path.is_file() else dest.stat().st_mtime
        data["finished_at"] = data.get("finished_at") or datetime.fromtimestamp(modified, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
        data["artifacts"] = _artifacts(dest)
    else:
        data.setdefault("artifacts", [])
    if dest or not isinstance(data.get("cleanup"), dict):
        data["cleanup"] = _cleanup_summary(cases, dest)
    owned = _read_json(dest / "owned.json") if dest else None
    data["resource_audit"] = {
        "registered": len(owned) if isinstance(owned, list) else 0,
        "owned": owned if isinstance(owned, list) else [],
    }
    data["passed"] = sum(row.get("status") == "pass" for row in cases)
    data["failed"] = sum(row.get("status") == "fail" for row in cases)
    data["skipped"] = sum(row.get("status") == "skip" for row in cases)
    data["interrupted"] = sum(row.get("status") == "interrupted" for row in cases)
    data["status"] = "fail" if data["failed"] else "interrupted" if data["interrupted"] else "pass" if data["passed"] else "skip" if data["skipped"] else "unknown"
    return data


def write_reports(dest: Path, results: list[Result], started: str, wall_s: float | None = None) -> None:
    payload = enrich_payload({
        "started": started,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "elapsed_s": round(wall_s if wall_s is not None else sum(result.elapsed_s for result in results), 3),
        "cases": [_result_payload(result) for result in results],
    }, dest)
    (dest / "report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    (dest / "report.md").write_text(markdown(payload), encoding="utf-8")
    (dest / "report.html").write_text(html_doc(payload), encoding="utf-8")


def _fingerprint(error: str) -> str:
    text = _UUID_RE.sub("<id>", error.strip())
    text = _HEX_RE.sub("<id>", text)
    return _ARGOS_NAME_RE.sub("<resource>", text) or "未记录失败原因"


def _error_groups(cases: list[dict]) -> list[dict]:
    groups = {}
    for case in cases:
        if case.get("status") not in {"fail", "interrupted"}:
            continue
        message = _fingerprint(str(case.get("error") or ""))
        row = groups.setdefault(message, {
            "message": message, "count": 0, "cases": set(), "iterations": [],
            "representative_case": str(case.get("id") or ""),
            "representative_iteration": int(case.get("iteration") or 1),
        })
        row["count"] += 1
        row["cases"].add(str(case.get("id") or ""))
        row["iterations"].append(int(case.get("iteration") or 1))
    return [{**row, "cases": sorted(row["cases"]), "iterations": sorted(row["iterations"])} for row in sorted(groups.values(), key=lambda item: item["count"], reverse=True)]


def _success_rate(data: dict) -> float | None:
    completed = int(data.get("passed") or 0) + int(data.get("failed") or 0)
    return 100 * int(data.get("passed") or 0) / completed if completed else None


def markdown(payload: dict) -> str:
    data = enrich_payload(payload)
    rate = _success_rate(data)
    errors = _error_groups(data["cases"])
    cleanup = data["cleanup"]
    lines = ["# Argos 测试报告", "", f"- 状态：{data['status']}", f"- 环境：{data.get('env') or '-'}", f"- 模式：{data.get('mode') or '-'}", f"- 开始：{data.get('started') or '-'}", f"- 结束：{data.get('finished_at') or '-'}", f"- 耗时：{fmt_dur(float(data.get('elapsed_s') or 0))}", f"- 结果：{data['passed']} 通过 / {data['failed']} 失败 / {data['skipped']} 跳过 / {data['interrupted']} 中断", f"- 成功率：{'—' if rate is None else f'{rate:.1f}%'}（不含跳过与中断）", "", "## 关键结论", ""]
    lines.append(f"- 主要问题：{errors[0]['message']}（{errors[0]['count']} 次）" if errors else "- 没有失败或中断轮次")
    lines.append(f"- 清理：{cleanup['status']}，成功 {cleanup['completed']}，失败 {cleanup['failed']}")
    lines.extend(["", "## 轮次详情", ""])
    for case in data["cases"]:
        lines.extend([f"### {case.get('id')} 第 {case.get('iteration') or 1} 轮 · {case.get('status')}", ""])
        if case.get("error"):
            lines.append(f"- 错误：{case['error']}")
        for step in case.get("steps") or []:
            duration = fmt_dur(step["elapsed_s"]) if step.get("elapsed_s") is not None else "耗时未记录"
            lines.append(f"- {step['name']}：{step_status(step, case)} · {duration} · {step.get('detail') or ''}")
            if step.get("status") in {"failed", "running"} and case.get("status") in {"fail", "interrupted"}:
                for operation in step.get("operations") or []:
                    if operation.get("type") == "command":
                        command = operation.get("operation") if isinstance(operation.get("operation"), dict) else {}
                        actual = operation.get("actual") if isinstance(operation.get("actual"), dict) else {}
                        lines.append(f"  - {'成功' if _operation_passed(operation) else '失败'} · `{_command_text(command.get('command'))}`")
                        lines.append(f"    - 返回码：{actual.get('returncode', '未记录')}")
                        if actual.get("stdout") or actual.get("output"):
                            lines.append(f"    - stdout：{str(actual.get('stdout') or actual.get('output')).strip()}")
                        if actual.get("stderr"):
                            lines.append(f"    - stderr：{str(actual.get('stderr')).strip()}")
                    else:
                        lines.append(f"  - 操作 {operation.get('label') or ''}：{json.dumps(operation.get('operation'), ensure_ascii=False, default=str)}")
                        lines.append(f"    - 判定规则：{json.dumps(operation.get('expected'), ensure_ascii=False, default=str)}")
                        lines.append(f"    - 响应：{json.dumps(operation.get('actual'), ensure_ascii=False, default=str)}")
                    for artifact in operation.get("artifacts") or []:
                        lines.append(f"    - 证据：{artifact}")
        lines.extend(f"- 备注：{note}" for note in case.get("notes") or [])
        lines.append("")
    return "\n".join(lines) + "\n"


def _operation_passed(operation: dict) -> bool:
    expected = operation.get("expected") if isinstance(operation.get("expected"), dict) else {}
    actual = operation.get("actual") if isinstance(operation.get("actual"), dict) else {}
    if operation.get("type") == "command":
        wanted, received = expected.get("returncode", 0), actual.get("returncode")
        return received != 0 if wanted == "nonzero" else received == wanted
    if operation.get("type") == "http":
        wanted, received = expected.get("http_status"), actual.get("http_status")
        return received in wanted if isinstance(wanted, (list, tuple)) else received == wanted
    return expected == actual


def _command_text(value: object) -> str:
    if not isinstance(value, list):
        return str(value or "历史运行未保存完整命令参数")
    masked = list(map(str, value))
    for index, item in enumerate(masked):
        lowered = item.lower()
        if index and masked[index - 1].lower() in {"-u", "--username", "-p", "--password"}:
            masked[index] = "***"
        elif lowered.startswith(("--password=", "--token=", "--secret=")):
            masked[index] = item.split("=", 1)[0] + "=***"
    return shlex.join(masked)


def html_doc(payload: dict) -> str:
    """Self-contained HTML shell: dash ReportView (prebuilt) + embedded report.json."""
    data = enrich_payload(payload)
    css_path = _STATIC_REPORT / "viewer.css"
    js_path = _STATIC_REPORT / "viewer.js"
    if not css_path.is_file() or not js_path.is_file():
        raise FileNotFoundError(
            f"missing report viewer at {_STATIC_REPORT}; run: npm run build:report (in dash/ui)"
        )
    css = css_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    payload_json = json.dumps(data, ensure_ascii=False, default=str).replace("<", "\\u003c")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1"/>\n'
        "<title>Argos 测试报告</title>\n"
        f"<style>{css}</style>\n"
        "</head>\n"
        '<body class="min-h-svh bg-background text-foreground antialiased">\n'
        '<div id="root"></div>\n'
        f'<script type="application/json" id="argos-report">{payload_json}</script>\n'
        f"<script>{js}</script>\n"
        "</body>\n"
        "</html>\n"
    )


def step_status(step: dict, case: dict) -> str:
    status = step.get("status", "")
    if status == "running" and case.get("status") in {"fail", "skip", "interrupted"}:
        return "未正常结束"
    return {"ok": "成功", "failed": "失败", "running": "执行中", "skip": "跳过"}.get(status, status)
