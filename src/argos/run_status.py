import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from argos.case import Result, Spec

LIVE = frozenset({"running", "paused"})
COUNTS = {"pass": "passed", "fail": "failed", "skip": "skipped", "interrupted": "interrupted"}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    os.replace(temporary, path)


class StopRequested(Exception):
    def __init__(self, message: str, results: list[Result] | None = None) -> None:
        super().__init__(message)
        self.results = list(results or [])


class RunStatus:
    def __init__(
        self,
        dest: Path,
        specs: list[Spec],
        *,
        title: str,
        mode: str,
        env: str,
        duration: str = "",
    ) -> None:
        self.path = dest / "status.json"
        self.control_path = dest / "control.json"
        self.paused_seconds = 0.0
        self.titles = {spec.id: spec.title for spec in specs}
        self.state = {
            "id": dest.name,
            "title": title,
            "mode": mode,
            "env": env,
            "duration": duration,
            "status": "running",
            "pid": os.getpid(),
            "started_at": _now(),
            "finished_at": "",
            "updated_at": _now(),
            "current_tasks": [],
            "total_cases": len(specs),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "interrupted": 0,
            "has_failure": False,
            "error": "",
        }
        self._write()

    def _write(self) -> None:
        self.state["updated_at"] = _now()
        _atomic_json(self.path, self.state)

    def _control_action(self) -> str:
        try:
            control = json.loads(self.control_path.read_text())
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return "run"
        return str(control.get("action") or "run")

    def stop_requested(self) -> bool:
        return self._control_action() == "stop"

    def on_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        if event_type == "start":
            self._wait_if_paused()
            if self.stop_requested():
                raise StopRequested("run stop requested")
        elif self._control_action() == "pause":
            self._wait_if_paused()
        case_id = str(event.get("id") or "")
        iteration = int(event.get("iteration") or 0)
        tasks: list[dict] = self.state["current_tasks"]
        if event_type == "start":
            tasks.append(
                {
                    "case_id": case_id,
                    "title": self.titles.get(case_id, case_id),
                    "iteration": iteration,
                    "step": "",
                }
            )
            self.state["status"] = "running"
        elif event_type == "step":
            task = next((row for row in tasks if row["case_id"] == case_id and row["iteration"] == iteration), None)
            if task is None:
                task = {"case_id": case_id, "title": self.titles.get(case_id, case_id), "iteration": iteration, "step": ""}
                tasks.append(task)
            task["step"] = str(event.get("name") or "")
            task["step_status"] = str(event.get("status") or "")
            task["detail"] = str(event.get("detail") or "")
        elif event_type == "end":
            result: Result | None = event.get("result")
            status = result.status if result is not None else str(event.get("status") or "fail")
            key = COUNTS.get(status, "failed")
            self.state[key] = int(self.state.get(key) or 0) + 1
            if status == "fail":
                self.state["has_failure"] = True
                self.state["error"] = (result.error if result is not None else str(event.get("error") or ""))[:1000]
            self.state["current_tasks"] = [
                row for row in tasks if not (row["case_id"] == case_id and row["iteration"] == iteration)
            ]
        self._write()

    def _wait_if_paused(self) -> None:
        began = 0.0
        while True:
            action = self._control_action()
            if action != "pause":
                if began:
                    self.paused_seconds += max(0.0, time.monotonic() - began)
                    self.state["status"] = "running"
                    self.state["paused_at"] = ""
                    self._write()
                if action == "stop":
                    raise StopRequested("run stop requested")
                return
            if not began:
                began = time.monotonic()
                self.state["status"] = "paused"
                self.state["paused_at"] = _now()
                self._write()
            time.sleep(0.5)

    def finish(self, status: str, error: str = "") -> None:
        self.state["status"] = status
        self.state["finished_at"] = _now()
        self.state["current_tasks"] = []
        if error:
            self.state["error"] = error[:1000]
        self._write()


def request_control(dest: Path, action: str) -> dict:
    if action not in {"pause", "resume", "stop"}:
        raise ValueError(f"unsupported run control: {action}")
    status_path = dest / "status.json"
    if not status_path.is_file():
        raise FileNotFoundError(dest.name)
    try:
        status = json.loads(status_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid run status: {dest.name}") from exc
    current = str(status.get("status") or "")
    if action == "pause" and current != "running":
        raise ValueError(f"cannot pause from {current}")
    if action == "resume" and current != "paused":
        raise ValueError(f"cannot resume from {current}")
    if action == "stop" and current not in LIVE:
        raise ValueError(f"cannot stop from {current}")
    requested = "pause" if action == "pause" else "stop" if action == "stop" else "run"
    _atomic_json(dest / "control.json", {"action": requested})
    status["status"] = "paused" if action == "pause" else "interrupted" if action == "stop" else "running"
    status["updated_at"] = _now()
    _atomic_json(status_path, status)
    return status
