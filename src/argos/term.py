import shutil
import sys
import time

from argos.case import Result, Spec

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
WHITE = "\033[37m"

STATUS_COLOR = {
    "pass": GREEN,
    "fail": RED,
    "skip": YELLOW,
    "running": CYAN,
}


def _c(color: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def width() -> int:
    return max(80, shutil.get_terminal_size((100, 24)).columns)


def fmt_dur(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:5.1f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m:2d}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def fmt_metrics(metrics: dict) -> str:
    if not metrics:
        return ""
    parts = []
    for key, value in metrics.items():
        parts.append(f"{key}={value}")
    return "  ".join(parts)


class Progress:
    def __init__(self, specs: list[Spec], run_dir: str):
        self.specs = {s.id: s for s in specs}
        self.order = [s.id for s in specs]
        self.run_dir = run_dir
        self.started = time.time()
        self.started_n = 0
        self.current: str = ""
        self.results: dict[str, Result] = {}
        self.history: list[Result] = []
        self.live_metrics: dict[str, dict] = {}
        self.live_steps: dict[str, list] = {}

    def on_event(self, event: dict) -> None:
        kind = event.get("type")
        cid = event.get("id", "")
        if kind == "pack":
            action = event.get("action")
            if action in {"run", "done"}:
                print(
                    f"    {DIM}pack {action}  {cid}  slots={event.get('slots')}  free={event.get('free')}{RESET}"
                    if sys.stdout.isatty()
                    else f"    pack {action}  {cid}  slots={event.get('slots')}  free={event.get('free')}",
                    flush=True,
                )
        elif kind == "start":
            self.started_n += 1
            self.current = cid
            iter_n = event.get("iteration") or 0
            extra = f"  iter {iter_n}" if iter_n else ""
            self._banner(cid, "RUNNING", CYAN, extra)
        elif kind == "metric":
            self.live_metrics.setdefault(cid, {})[event["key"]] = event["value"]
        elif kind == "step":
            steps = self.live_steps.setdefault(cid, [])
            row = (event["name"], event["status"], event.get("detail") or "")
            prev = None
            for i, existing in enumerate(steps):
                if existing[0] == row[0]:
                    prev = existing
                    steps[i] = row
                    break
            else:
                steps.append(row)
            if prev != row:
                self._live_line(cid)
        elif kind == "note":
            print(
                f"    {DIM}{event.get('message')}{RESET}" if sys.stdout.isatty() else f"    {event.get('message')}",
                flush=True,
            )
        elif kind == "end":
            result: Result = event["result"]
            self.results[cid] = result
            self.history.append(result)
            self._finish(result)

    def _banner(self, cid: str, label: str, color: str, extra: str = "") -> None:
        spec = self.specs[cid]
        n = self.started_n
        total = len(self.order)
        prefix = f"[{n}] " if extra else f"[{n}/{total}] "
        print(flush=True)
        print(_c(BOLD, prefix) + _c(color + BOLD, label) + f"  {spec.id}  " + _c(DIM, spec.title + extra), flush=True)

    def _live_line(self, cid: str) -> None:
        metrics = fmt_metrics(self.live_metrics.get(cid, {}))
        steps = self.live_steps.get(cid) or []
        last = steps[-1] if steps else ("", "", "")
        unit = f"{last[0]}:{last[1]}" if last[0] else ""
        line = "    " + "  ".join(p for p in (cid, unit, metrics) if p)
        if line.strip():
            print(_c(DIM, line) if sys.stdout.isatty() else line, flush=True)

    def _finish(self, result: Result) -> None:
        color = STATUS_COLOR.get(result.status, WHITE)
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(result.status, result.status.upper())
        extra = fmt_metrics(result.metrics)
        err = f"  {result.error}" if result.error and result.status == "fail" else ""
        print(
            "    "
            + _c(color + BOLD, mark)
            + f"  {fmt_dur(result.elapsed_s)}"
            + (f"  {extra}" if extra else "")
            + _c(DIM, err)
        )

    def summary(self) -> None:
        rows = self.history or list(self.results.values())
        passed = sum(1 for r in rows if r.status == "pass")
        failed = sum(1 for r in rows if r.status == "fail")
        skipped = sum(1 for r in rows if r.status == "skip")
        elapsed = time.time() - self.started
        print()
        print(_c(BOLD, "─" * min(width(), 100)))
        print(_c(BOLD, "Results"))
        print(f"{'ID':<32} {'ITER':>4} {'STAT':<6} {'TIME':>8}  METRICS")
        for result in rows:
            color = STATUS_COLOR.get(result.status, WHITE)
            iter_s = str(result.iteration or 1)
            print(
                f"{result.spec.id:<32} "
                f"{iter_s:>4} "
                + _c(color, f"{result.status:<6}")
                + f" {fmt_dur(result.elapsed_s):>8}  {fmt_metrics(result.metrics)}"
            )
        print()
        bar_pass = _c(GREEN, f"{passed} pass")
        bar_fail = _c(RED, f"{failed} fail")
        bar_skip = _c(YELLOW, f"{skipped} skip")
        print(f"{bar_pass}  {bar_fail}  {bar_skip}  / {len(rows)}    {fmt_dur(elapsed)}    {self.run_dir}")
