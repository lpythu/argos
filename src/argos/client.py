import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

DEFAULT_DASH = "https://argos.saidc.ai"


def dash_url(override: str = "") -> str:
    raw = (override or os.environ.get("ARGOS_DASH_URL") or DEFAULT_DASH).strip()
    return raw.rstrip("/")


def dash_token() -> str:
    return (os.environ.get("ARGOS_TOKEN") or "").strip()


class DashError(RuntimeError):
    pass


class Client:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def create_run(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._json("POST", "/api/runs", body)

    def post_events(self, run_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        return self._json("POST", f"/api/runs/{run_id}/events", {"events": events})

    def finish(self, run_id: str, report: dict[str, Any], status: str) -> dict[str, Any]:
        return self._json("POST", f"/api/runs/{run_id}/finish", {"report": report, "status": status})

    def upload_file(self, run_id: str, rel: str, text: str) -> dict[str, Any]:
        return self._json("POST", f"/api/runs/{run_id}/files", {"path": rel, "text": text})

    def browse_url(self, run_id: str) -> str:
        return f"{self.base}/runs/{run_id}"

    def _json(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(
            urljoin(self.base + "/", path.lstrip("/")),
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {self.token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DashError(f"{method} {path} -> {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DashError(f"{method} {path}: {exc.reason}") from exc
        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise DashError(f"{method} {path}: expected object")
        return parsed


def push_dir(client: Client, dest: Path) -> str:
    run_meta = _read_json(dest / "run.json")
    report = _read_json(dest / "report.json")
    created = client.create_run({**run_meta, "status": "running"})
    run_id = str(created["id"])
    events_path = dest / "events.jsonl"
    if events_path.is_file():
        rows = [_parse_event(line) for line in events_path.read_text().splitlines() if line.strip()]
        if rows:
            client.post_events(run_id, rows)
    status = "fail" if report.get("failed") else "pass"
    if report:
        client.finish(run_id, report, status)
    for path in dest.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(dest).as_posix()
        if rel in {"events.jsonl"}:
            continue
        if path.stat().st_size > 256_000:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        client.upload_file(run_id, rel, text)
    return run_id


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text())
    return raw if isinstance(raw, dict) else {}


def _parse_event(line: str) -> dict[str, Any]:
    row = json.loads(line)
    return row if isinstance(row, dict) else {"raw": line}
