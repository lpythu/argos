"""Structured common report renderer used by every Argos case."""

import copy
import html
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from argos.case import Result
from argos.term import fmt_dur

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


def _display_time(value: object) -> str:
    text = str(value or "")
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", text)
    if match:
        return f"{match[1]}-{match[2]}-{match[3]} {match[4]}:{match[5]}:{match[6]}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text or "—"


def _size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


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


def _artifact_href(path: str, artifact_base: str) -> str:
    return f"{artifact_base}{quote(path)}" if artifact_base else quote(path)


def _pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str) if isinstance(value, (dict, list)) else str(value or "—")


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


def _artifact_links(operation: dict, artifact_base: str) -> str:
    return "".join(
        f"<a href='{html.escape(_artifact_href(str(path), artifact_base), quote=True)}' target='_blank'>{html.escape(Path(str(path)).name)}</a>"
        for path in operation.get("artifacts") or []
    )


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


def _command_html(operation: dict, artifact_base: str) -> str:
    actual = operation.get("actual") if isinstance(operation.get("actual"), dict) else {}
    command = operation.get("operation") if isinstance(operation.get("operation"), dict) else {}
    passed = _operation_passed(operation)
    status = "成功" if passed else "失败"
    css = "ok" if passed else "failed"
    opened = "" if passed else " open"
    stdout = str(actual.get("stdout") or actual.get("output") or "")
    stderr = str(actual.get("stderr") or "")
    elapsed = operation.get("elapsed_s")
    links = _artifact_links(operation, artifact_base)
    legacy = ""
    output = "".join([
        f"<div><span>返回码</span><pre>{html.escape(str(actual.get('returncode', '未记录')))}</pre></div>",
        f"<div><span>stdout</span><pre>{html.escape(stdout or '—')}</pre></div>",
        f"<div class='actual'><span>stderr</span><pre>{html.escape(stderr or '—')}</pre></div>",
    ])
    return f"<details class='operation command'{opened}><summary><span class='st {css}'>{status}</span> <b>{html.escape(str(operation.get('label') or 'Command'))}</b> {legacy}<code>$ {html.escape(_command_text(command.get('command')))}</code></summary><div class='command-output'>{output}</div><div class='command-meta'>{f'耗时：{html.escape(fmt_dur(float(elapsed)))}' if elapsed is not None else ''}{f' 完整日志：{links}' if links else ''}</div></details>"


def _operation_html(operation: dict, artifact_base: str) -> str:
    if operation.get("type") == "command":
        return _command_html(operation, artifact_base)
    label = html.escape(str(operation.get("label") or "操作"))
    kind = html.escape(str(operation.get("type") or "operation"))
    request = html.escape(_pretty(operation.get("operation")))
    expected = html.escape(_pretty(operation.get("expected")))
    actual = html.escape(_pretty(operation.get("actual")))
    links = _artifact_links(operation, artifact_base)
    legacy = ""
    passed = _operation_passed(operation)
    return f"<details class='operation'{' open' if not passed else ''}><summary><span class='st {'ok' if passed else 'failed'}'>{'成功' if passed else '失败'}</span> <b>{label}</b> <span class='chip'>{kind}</span>{legacy}</summary><div class='evidence-grid'><div><span>请求</span><pre>{request}</pre></div><div><span>判定规则</span><pre>{expected}</pre></div><div class='actual'><span>响应</span><pre>{actual}</pre></div></div>{f'<div class="evidence-links">证据文件：{links}</div>' if links else ''}</details>"


def _case_anchor(case_id: object, iteration: object) -> str:
    return "case-" + re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{case_id}-{iteration}").strip("-")


def html_doc(payload: dict, *, artifact_base: str = "") -> str:
    data = enrich_payload(payload)
    cases, cleanup = data["cases"], data["cleanup"]
    errors, rate = _error_groups(cases), _success_rate(data)
    status_label = {"pass": "通过", "fail": "失败", "skip": "跳过", "interrupted": "中断"}.get(data["status"], data["status"])
    cleanup_label = {"pass": "成功", "fail": "失败", "unknown": "未涉及"}.get(cleanup["status"], cleanup["status"])
    planned = data.get("duration") or ("历史记录未记录" if data.get("mode") == "soak" else "单轮")
    top_error = errors[0] if errors else None
    conclusion = f"主要问题：{top_error['message']}，共出现 {top_error['count']} 次。" if top_error else "所有已完成轮次均未发现失败。"
    conclusion += f" 有 {cleanup['failed']} 个清理阶段失败。" if cleanup["status"] == "fail" else " 已记录的资源清理均成功。" if cleanup["status"] == "pass" else ""
    representative_keys = {
        (row["representative_case"], row["representative_iteration"])
        for row in errors
    }
    error_rows = "".join(
        f"<tr><td>{html.escape(row['message'])}</td><td><code>{html.escape('、'.join(row['cases']))}</code></td><td class='num'>{row['count']}</td><td>{html.escape('、'.join(map(str,row['iterations'])))}</td><td><a href='#{_case_anchor(row['representative_case'], row['representative_iteration'])}'>查看代表失败</a></td></tr>"
        for row in errors
    )
    blocks = []
    for case in cases:
        metrics = "".join(f'<span class="chip">{html.escape(str(k))}={html.escape(str(v))}</span>' for k,v in (case.get("metrics") or {}).items()) or '<span class="muted">无指标</span>'
        step_rows = "".join(
            f"<tr><td>{html.escape(str(s.get('name') or ''))}</td><td><span class='st {html.escape(str(s.get('status') or ''))}'>{html.escape(step_status(s,case))}</span></td><td class='num'>{html.escape(fmt_dur(s['elapsed_s']) if s.get('elapsed_s') is not None else '—')}</td><td>{html.escape(str(s.get('detail') or ''))}{''.join(_operation_html(op, artifact_base) for op in s.get('operations') or [] if isinstance(op,dict)) if s.get('status') in {'failed','running'} and case.get('status') in {'fail','interrupted'} else ''}</td></tr>"
            for s in case.get("steps") or []
        )
        notes = "".join(f"<li>{html.escape(str(note))}</li>" for note in case.get("notes") or [])
        error = f"<div class='error-box'>{html.escape(str(case.get('error')))}</div>" if case.get("error") else ""
        case_key = (str(case.get("id") or ""), int(case.get("iteration") or 1))
        opened = " open" if case_key in representative_keys or case.get("status") == "interrupted" else ""
        blocks.append(f"<details id='{_case_anchor(*case_key)}' class='iteration'{opened}><summary><span class='st {html.escape(str(case.get('status') or ''))}'>{html.escape(str(case.get('status') or ''))}</span> <b>{html.escape(str(case.get('id') or ''))}</b> · 第 {case.get('iteration') or 1} 轮 <span class='summary-time'>{html.escape(fmt_dur(float(case.get('elapsed_s') or 0)))}</span></summary><div class='iteration-body'>{error}<div class='metrics'>{metrics}</div><table><thead><tr><th>阶段</th><th>状态</th><th>耗时</th><th>说明与失败操作</th></tr></thead><tbody>{step_rows}</tbody></table>{f'<h4>备注与清理结果</h4><ul>{notes}</ul>' if notes else ''}</div></details>")
    artifact_rows = "".join(f"<tr><td><a href='{html.escape(_artifact_href(row['path'],artifact_base),quote=True)}' target='_blank'>{html.escape(row['path'])}</a></td><td class='num'>{html.escape(_size(int(row['bytes'])))}</td></tr>" for row in data.get("artifacts") or [])
    total = max(1, data["passed"]+data["failed"]+data["skipped"]+data["interrupted"])
    queries = "、".join(map(str, data.get("queries") or []))
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Argos 测试报告</title><style>
:root{{color-scheme:dark;--bg:#0d1319;--panel:#18212b;--line:#2b3947;--text:#e8eef4;--muted:#91a0af;--green:#42d392;--red:#ff7171;--yellow:#f4c95d;--blue:#62b6ff}}*{{box-sizing:border-box}}body{{font:14px/1.5 ui-sans-serif,system-ui;margin:0;background:var(--bg);color:var(--text)}}main{{max-width:1440px;margin:auto;padding:28px}}h1,h2,h4{{margin-top:0}}h2{{font-size:17px;margin-bottom:14px}}.header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}}.header h1{{margin-bottom:5px}}.badge,.chip{{display:inline-block;border-radius:999px;padding:3px 9px;background:#263443;margin:0 5px 5px 0;font-size:12px}}.badge{{font-weight:700}}.badge.pass,.good,.st.ok,.st.pass{{color:var(--green)}}.badge.fail,.bad,.st.failed,.st.fail{{color:var(--red)}}.badge.interrupted,.st.interrupted,.st.skip{{color:var(--yellow)}}.meta,.cards{{display:grid;gap:10px}}.meta{{grid-template-columns:repeat(6,minmax(120px,1fr));margin:18px 0}}.meta div,.card,.section{{background:var(--panel);border:1px solid var(--line);border-radius:12px}}.meta div{{padding:11px 13px}}.meta b,.meta span{{display:block}}.meta span,.muted,.sub{{color:var(--muted);font-size:12px}}.cards{{grid-template-columns:repeat(6,minmax(105px,1fr));margin:12px 0 16px}}.card{{padding:13px 15px}}.card b{{display:block;font-size:24px}}.bar{{display:flex;height:8px;overflow:hidden;border-radius:99px;background:#25313d;margin-bottom:18px}}.bar i{{display:block}}.bar .p{{width:{100*data['passed']/total:.2f}%;background:var(--green)}}.bar .f{{width:{100*data['failed']/total:.2f}%;background:var(--red)}}.bar .s{{width:{100*data['skipped']/total:.2f}%;background:var(--yellow)}}.bar .i{{width:{100*data['interrupted']/total:.2f}%;background:#9b87f5}}.section{{padding:18px;margin:14px 0}}.conclusion{{border-left:4px solid {'var(--red)' if errors else 'var(--green)'};font-size:15px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:var(--muted);font-weight:600}}.num{{font-variant-numeric:tabular-nums}}.st{{text-transform:uppercase;font-weight:750}}.iteration{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:9px 0;overflow:hidden;scroll-margin-top:12px}}summary{{padding:13px 15px;cursor:pointer}}.summary-time{{float:right;color:var(--muted)}}.iteration-body{{padding:0 15px 15px}}.metrics{{margin:10px 0}}.error-box{{background:#3a2026;color:#ffc1c1;border-radius:8px;padding:10px 12px;margin:8px 0 12px;white-space:pre-wrap}}.operation{{margin:8px 0;border:1px solid var(--line);border-radius:8px;background:#111922}}.operation summary{{padding:8px 10px}}.command summary code{{display:block;margin:6px 0 0;color:#dce7f0;white-space:pre-wrap;word-break:break-word}}.command-output{{display:grid;grid-template-columns:.45fr 1fr 1.4fr;gap:8px;padding:0 10px 10px}}.command-output span,.evidence-grid span{{display:block;color:var(--muted);font-size:11px;margin-bottom:3px}}.command-meta{{padding:0 10px 10px;color:var(--muted)}}.evidence-grid{{display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:8px;padding:0 10px 10px}}.evidence-grid>div,.command-output>div{{min-width:0}}pre{{margin:0;max-height:260px;overflow:auto;white-space:pre-wrap;word-break:break-word;background:#0a1016;border-radius:6px;padding:8px;color:#dce7f0}}.actual pre,.command.failed .actual pre{{color:#ffc1c1}}.evidence-links{{padding:0 10px 10px}}.evidence-links a,.command-meta a{{margin-left:8px}}.artifacts>summary h2{{display:inline;margin:0}}a{{color:var(--blue)}}ul{{margin-bottom:0}}@media(max-width:900px){{main{{padding:16px}}.header{{display:block}}.meta,.cards{{grid-template-columns:repeat(2,1fr)}}.section{{overflow:auto}}.evidence-grid,.command-output{{grid-template-columns:1fr}}}}
</style></head><body><main><div class="header"><div><h1>Argos 测试报告</h1><div class="sub">{html.escape(queries)}</div></div><span class="badge {html.escape(data['status'])}">{html.escape(status_label)}</span></div><div class="meta"><div><span>环境</span><b>{html.escape(str(data.get('env') or '—'))}</b></div><div><span>模式</span><b>{html.escape(str(data.get('mode') or '—'))}</b></div><div><span>开始时间</span><b>{html.escape(_display_time(data.get('started')))}</b></div><div><span>结束时间</span><b>{html.escape(_display_time(data.get('finished_at')))}</b></div><div><span>运行耗时</span><b>{html.escape(fmt_dur(float(data.get('elapsed_s') or 0)))}</b></div><div><span>计划时长</span><b>{html.escape(str(planned))}</b></div></div><div class="cards"><div class="card good"><b>{data['passed']}</b>通过</div><div class="card bad"><b>{data['failed']}</b>失败</div><div class="card"><b>{data['skipped']}</b>跳过</div><div class="card"><b>{data['interrupted']}</b>中断</div><div class="card"><b>{'—' if rate is None else f'{rate:.1f}%'}</b>成功率</div><div class="card"><b>{html.escape(str(cleanup_label))}</b>清理状态</div></div><div class="bar"><i class="p"></i><i class="f"></i><i class="s"></i><i class="i"></i></div><section class="section conclusion"><h2>关键结论</h2>{html.escape(conclusion)}</section><section class="section"><h2>错误聚合</h2>{f'<table><thead><tr><th>错误指纹</th><th>影响用例</th><th>次数</th><th>轮次</th><th>操作</th></tr></thead><tbody>{error_rows}</tbody></table>' if error_rows else '<div class="muted">没有失败或中断记录</div>'}</section><section class="section"><h2>轮次详情</h2>{''.join(blocks)}</section><section class="section"><h2>清理结果</h2><div class="cards"><div class="card"><b>{cleanup['completed']}</b>清理成功</div><div class="card"><b>{cleanup['failed']}</b>清理失败</div></div></section><details class="section artifacts"><summary><h2>查看全部产物</h2></summary>{f'<table><thead><tr><th>文件</th><th>大小</th></tr></thead><tbody>{artifact_rows}</tbody></table>' if artifact_rows else '<div class="muted">没有可展示的产物</div>'}</details></main></body></html>"""


def step_status(step: dict, case: dict) -> str:
    status = step.get("status", "")
    if status == "running" and case.get("status") in {"fail", "skip", "interrupted"}:
        return "未正常结束"
    return {"ok": "成功", "failed": "失败", "running": "执行中", "skip": "跳过"}.get(status, status)
