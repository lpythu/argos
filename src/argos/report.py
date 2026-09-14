import html
import json
from pathlib import Path

from argos.case import Result
from argos.term import fmt_dur


def write_reports(dest: Path, results: list[Result], started: str, wall_s: float | None = None) -> None:
    payload = {
        "started": started,
        "passed": sum(1 for r in results if r.status == "pass"),
        "failed": sum(1 for r in results if r.status == "fail"),
        "skipped": sum(1 for r in results if r.status == "skip"),
        "elapsed_s": round(wall_s if wall_s is not None else sum(r.elapsed_s for r in results), 3),
        "cases": [
            {
                "id": r.spec.id,
                "slug": r.spec.slug,
                "iteration": r.iteration,
                "title": r.spec.title,
                "group": r.spec.group,
                "pack": r.spec.pack,
                "tags": list(r.spec.tags),
                "modes": list(r.spec.modes),
                "status": r.status,
                "elapsed_s": round(r.elapsed_s, 3),
                "error": r.error,
                "metrics": r.metrics,
                "steps": [s.__dict__ for s in r.steps],
                "notes": r.notes,
                "dest": r.dest,
            }
            for r in results
        ],
    }
    (dest / "report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    (dest / "report.md").write_text(markdown(payload), encoding="utf-8")
    (dest / "report.html").write_text(html_doc(payload), encoding="utf-8")


def markdown(payload: dict) -> str:
    lines = [
        "# argos report",
        "",
        f"- started: {payload['started']}",
        f"- pass {payload['passed']} / fail {payload['failed']} / skip {payload['skipped']}",
        f"- elapsed {fmt_dur(payload['elapsed_s'])}",
        "",
        "| ID | Slug | Iter | Status | Time | Metrics | Error |",
        "|---|---|---:|---|---:|---|---|",
    ]
    for case in payload["cases"]:
        metrics = ", ".join(f"{k}={v}" for k, v in (case.get("metrics") or {}).items())
        err = (case.get("error") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{case['id']}` | `{case.get('slug') or case['id']}` | {case.get('iteration') or 1} | {case['status']} | {fmt_dur(case['elapsed_s'])} | {metrics} | {err} |"
        )
    return "\n".join(lines) + "\n"


def html_doc(payload: dict) -> str:
    rows = []
    for case in payload["cases"]:
        metrics = "".join(
            f'<span class="chip">{html.escape(str(k))}={html.escape(str(v))}</span>'
            for k, v in (case.get("metrics") or {}).items()
        )
        steps = "".join(
            f'<li><b>{html.escape(s["name"])}</b> {html.escape(s["status"])} {html.escape(s.get("detail") or "")}</li>'
            for s in case.get("steps") or []
        )
        err = html.escape(case.get("error") or "")
        slug = html.escape(case.get("slug") or case["id"])
        rows.append(
            f"""<tr class="{html.escape(case['status'])}">
            <td><code>{html.escape(case['id'])}</code><div class="sub">#{case.get('iteration') or 1} {slug} · {html.escape(case['title'])}</div></td>
            <td class="st">{html.escape(case['status'])}</td>
            <td class="num">{html.escape(fmt_dur(case['elapsed_s']))}</td>
            <td>{metrics}</td>
            <td class="err">{err}<ol>{steps}</ol></td>
            </tr>"""
        )
    passed, failed, skipped = payload["passed"], payload["failed"], payload["skipped"]
    total = max(1, passed + failed + skipped)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<title>argos report</title>
<style>
body {{ font: 14px/1.45 ui-sans-serif, system-ui; margin: 24px; background: #0f1419; color: #e7ecf1; }}
h1 {{ font-size: 20px; margin: 0 0 12px; }}
.cards {{ display: flex; gap: 12px; margin: 16px 0 24px; }}
.card {{ background: #1a222c; border-radius: 10px; padding: 12px 16px; min-width: 110px; }}
.card b {{ display: block; font-size: 22px; }}
.pass b {{ color: #3dd68c; }} .fail b {{ color: #ff6b6b; }} .skip b {{ color: #f5c542; }}
.bar {{ height: 8px; background: #2a3340; border-radius: 99px; overflow: hidden; display: flex; margin-bottom: 20px; }}
.bar i {{ display: block; height: 100%; }}
.bar .p {{ background: #3dd68c; width: {100 * passed / total:.1f}%; }}
.bar .f {{ background: #ff6b6b; width: {100 * failed / total:.1f}%; }}
.bar .s {{ background: #f5c542; width: {100 * skipped / total:.1f}%; }}
table {{ width: 100%; border-collapse: collapse; background: #1a222c; border-radius: 10px; overflow: hidden; }}
th, td {{ text-align: left; padding: 10px 12px; vertical-align: top; border-bottom: 1px solid #2a3340; }}
th {{ color: #9aa8b5; font-weight: 600; }}
.st {{ text-transform: uppercase; font-weight: 700; }}
tr.pass .st {{ color: #3dd68c; }} tr.fail .st {{ color: #ff6b6b; }} tr.skip .st {{ color: #f5c542; }}
.sub {{ color: #8b98a5; font-size: 12px; margin-top: 2px; }}
.chip {{ display: inline-block; background: #2a3340; border-radius: 99px; padding: 2px 8px; margin: 0 4px 4px 0; font-size: 12px; }}
.err {{ color: #ffb4b4; font-size: 12px; max-width: 360px; }}
ol {{ margin: 6px 0 0; padding-left: 18px; color: #c5d0da; }}
.num {{ font-variant-numeric: tabular-nums; }}
</style></head><body>
<h1>argos report</h1>
<div class="sub">{html.escape(payload['started'])} · {html.escape(fmt_dur(payload['elapsed_s']))}</div>
<div class="cards">
  <div class="card pass"><b>{passed}</b>pass</div>
  <div class="card fail"><b>{failed}</b>fail</div>
  <div class="card skip"><b>{skipped}</b>skip</div>
</div>
<div class="bar"><i class="p"></i><i class="f"></i><i class="s"></i></div>
<table>
<thead><tr><th>Case</th><th>Status</th><th>Time</th><th>Metrics</th><th>Detail</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>
</body></html>
"""
