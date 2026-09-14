import json
import math
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ONCE = "once"
SOAK = "soak"

_OWNERSHIP_LOCK = threading.Lock()
_SENSITIVE = ("authorization", "cookie", "password", "passwd", "token", "secret")


def case_slug(case_id: str) -> str:
    return case_id.replace(":", "-")


def run_slug(ids: list[str]) -> str:
    if not ids:
        return "empty"
    if len(ids) == 1:
        return case_slug(ids[0])
    groups = {part.split(":", 1)[0] if ":" in part else part for part in ids}
    if len(groups) == 1:
        return next(iter(groups))
    if len(ids) <= 3:
        return "+".join(case_slug(i) for i in ids)
    return f"{len(ids)}-cases"


@dataclass(frozen=True)
class Spec:
    id: str
    title: str
    group: str
    tags: tuple[str, ...] = ()
    modes: tuple[str, ...] = (ONCE,)
    pack: str = ""

    @property
    def slug(self) -> str:
        return case_slug(self.id)


@dataclass
class Step:
    name: str
    status: str
    detail: str = ""
    started_at: str = ""
    ended_at: str = ""
    elapsed_s: float | None = None
    operations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Result:
    spec: Spec
    status: str
    elapsed_s: float
    error: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dest: str = ""
    iteration: int = 0
    metric_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    samples: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    distributions: dict[str, dict[str, Any]] = field(default_factory=dict)
    thresholds: list[dict[str, Any]] = field(default_factory=list)


class Skip(Exception):
    pass


class Fail(Exception):
    pass


class Context:
    def __init__(
        self,
        spec: Spec,
        dest: Path,
        emit: Callable[[dict], None],
        *,
        iteration: int = 0,
        run_dest: Path | None = None,
        mode: str = ONCE,
    ):
        self.spec = spec
        self.dest = dest
        self.dest.mkdir(parents=True, exist_ok=True)
        self.iteration = iteration
        self.run_dest = run_dest or dest.parent
        self.mode = mode
        self.metrics: dict[str, Any] = {}
        self.metric_meta: dict[str, dict[str, Any]] = {}
        self.samples: dict[str, list[dict[str, Any]]] = {}
        self.distributions: dict[str, dict[str, Any]] = {}
        self.thresholds: list[dict[str, Any]] = []
        self.steps: list[Step] = []
        self.notes: list[str] = []
        self._emit = emit
        self._step_clocks: dict[str, float] = {}
        self.write(
            "case.json",
            {
                "id": spec.id,
                "slug": spec.slug,
                "title": spec.title,
                "group": spec.group,
                "pack": spec.pack,
                "tags": list(spec.tags),
                "modes": list(spec.modes),
            },
        )

    def metric(self, key: str, value: Any, *, unit: str = "", kind: str = "gauge", scope: str = "iteration") -> None:
        self.metrics[key] = value
        self.metric_meta[key] = {"unit": unit, "kind": kind, "scope": scope}
        self._dump()
        self._emit(
            {
                "type": "metric",
                "id": self.spec.id,
                "iteration": self.iteration,
                "key": key,
                "value": value,
                "unit": unit,
                "kind": kind,
                "scope": scope,
            }
        )

    def sample(
        self,
        name: str,
        value: float,
        *,
        unit: str = "",
        timestamp: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> None:
        point = {
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "value": float(value),
            "labels": dict(labels or {}),
        }
        points = self.samples.setdefault(name, [])
        points.append(point)
        if len(points) > 1000:
            del points[:-1000]
        self.metric_meta[name] = {"unit": unit, "kind": "sample", "scope": "iteration"}
        self._dump()
        self._emit({"type": "metric_sample", "id": self.spec.id, "iteration": self.iteration, "name": name, "unit": unit, **point})

    def distribution(self, name: str, values: list[float], *, unit: str = "") -> None:
        clean = sorted(float(value) for value in values if math.isfinite(float(value)))
        if not clean:
            return

        def percentile(fraction: float) -> float:
            index = max(0, math.ceil(fraction * len(clean)) - 1)
            return clean[index]

        summary = {
            "count": len(clean),
            "min": clean[0],
            "avg": statistics.fmean(clean),
            "p50": percentile(0.50),
            "p90": percentile(0.90),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
            "max": clean[-1],
            "unit": unit,
        }
        self.distributions[name] = {
            key: round(value, 6) if isinstance(value, float) else value for key, value in summary.items()
        }
        self.metric_meta[name] = {"unit": unit, "kind": "distribution", "scope": "iteration"}
        self._dump()
        self._emit({"type": "distribution", "id": self.spec.id, "iteration": self.iteration, "name": name, **self.distributions[name]})

    def threshold(self, name: str, *, actual: float, operator: str, target: float, unit: str = "") -> bool:
        checks = {">=": actual >= target, ">": actual > target, "<=": actual <= target, "<": actual < target, "==": actual == target}
        if operator not in checks:
            raise ValueError(f"unsupported threshold operator: {operator}")
        row = {"name": name, "actual": actual, "operator": operator, "target": target, "unit": unit, "passed": checks[operator]}
        self.thresholds.append(row)
        self._dump()
        self._emit({"type": "threshold", "id": self.spec.id, "iteration": self.iteration, **row})
        return bool(row["passed"])

    def note(self, message: str) -> None:
        self.notes.append(message)
        self._emit({"type": "note", "id": self.spec.id, "message": message})

    def step(self, name: str, status: str = "ok", detail: str = "") -> None:
        row = Step(name=name, status=status, detail=detail)
        now = datetime.now(timezone.utc).isoformat()
        old = next((item for item in self.steps if item.name == name), None)
        row.started_at = old.started_at if old else now
        row.operations = list(old.operations) if old else []
        self._step_clocks.setdefault(name, time.monotonic())
        if status != "running":
            row.ended_at = now
            row.elapsed_s = round(time.monotonic() - self._step_clocks[name], 3)
        for i, existing in enumerate(self.steps):
            if existing.name == name:
                self.steps[i] = row
                break
        else:
            self.steps.append(row)
        self._dump()
        self._emit({"type": "step", "id": self.spec.id, "iteration": self.iteration, **row.__dict__})

    @staticmethod
    def _safe_evidence(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): "***" if any(word in str(key).lower() for word in _SENSITIVE) else Context._safe_evidence(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [Context._safe_evidence(item) for item in value]
        return value

    def _active_step(self, step_name: str = "") -> Step:
        if step_name:
            target = next((row for row in reversed(self.steps) if row.name == step_name), None)
        else:
            target = next((row for row in reversed(self.steps) if row.status == "running"), None)
        if target is None:
            raise RuntimeError(f"cannot record operation without an active step: {step_name or 'running'}")
        return target

    def operation(
        self,
        label: str,
        *,
        kind: str,
        operation: Any,
        expected: Any,
        actual: Any,
        artifacts: list[str] | None = None,
        step_name: str = "",
    ) -> None:
        target = self._active_step(step_name)
        row = {
            "label": label,
            "type": kind,
            "operation": self._safe_evidence(operation),
            "expected": self._safe_evidence(expected),
            "actual": self._safe_evidence(actual),
            "artifacts": list(artifacts or []),
        }
        target.operations.append(row)
        self._dump()
        self._emit({"type": "operation", "id": self.spec.id, "iteration": self.iteration, "step": target.name, "operation": row})

    def command_operation(
        self,
        label: str,
        command: list[str],
        *,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        expected_returncode: int | str = 0,
        artifact: str = "",
        step_name: str = "",
        elapsed_s: float | None = None,
    ) -> None:
        safe = list(command)
        for index, value in enumerate(safe):
            lowered = str(value).lower()
            if index and str(safe[index - 1]).lower() in {"-u", "--username", "-p", "--password"}:
                safe[index] = "***"
            elif lowered.startswith(("--password=", "--token=", "--secret=")):
                safe[index] = lowered.split("=", 1)[0] + "=***"
        self.operation(
            label,
            kind="command",
            operation={"command": safe},
            expected={"returncode": expected_returncode},
            actual={"returncode": returncode, "stdout": stdout[-12000:], "stderr": stderr[-12000:]},
            artifacts=[artifact] if artifact else [],
            step_name=step_name,
        )
        if elapsed_s is not None:
            self._active_step(step_name).operations[-1]["elapsed_s"] = round(elapsed_s, 3)
            self._dump()

    def http_operation(
        self,
        label: str,
        method: str,
        url: str,
        *,
        request: Any,
        status: int,
        body: Any,
        expected_status: int | list[int] | tuple[int, ...],
        artifact: str = "",
        step_name: str = "",
    ) -> None:
        self.operation(
            label,
            kind="http",
            operation={"method": method, "url": url, "request": request},
            expected={"http_status": expected_status},
            actual={"http_status": status, "body": body},
            artifacts=[artifact] if artifact else [],
            step_name=step_name,
        )

    def fail_running(self, message: str) -> None:
        for row in list(self.steps):
            if row.status == "running":
                self.step(row.name, "failed", message)

    def check(self, ok: bool, message: str) -> None:
        if not ok:
            raise Fail(message)

    def skip(self, message: str) -> None:
        raise Skip(message)

    def fail(self, message: str) -> None:
        raise Fail(message)

    def own(self, resource_id: str, catalog_id: str = "") -> None:
        with _OWNERSHIP_LOCK:
            path = self.run_dest / "owned.json"
            rows: list[dict[str, str]] = []
            if path.exists():
                raw = json.loads(path.read_text())
                if isinstance(raw, list):
                    rows = [row for row in raw if isinstance(row, dict)]
            if any(row.get("id") == resource_id for row in rows):
                return
            rows.append({"id": resource_id, "catalog_id": catalog_id})
            path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")

    def write(self, name: str, obj: Any) -> Path:
        path = self.dest / name
        if isinstance(obj, (bytes, bytearray)):
            path.write_bytes(obj)
        elif isinstance(obj, str):
            path.write_text(obj)
        else:
            path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
        return path

    def _dump(self) -> None:
        self.write(
            "progress.json",
            {
                "id": self.spec.id,
                "slug": self.spec.slug,
                "title": self.spec.title,
                "metrics": self.metrics,
                "metric_meta": self.metric_meta,
                "samples": self.samples,
                "distributions": self.distributions,
                "thresholds": self.thresholds,
                "steps": [step.__dict__ for step in self.steps],
                "notes": self.notes,
            },
        )
