import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from argos.secrets import secrets_dir


@dataclass(frozen=True)
class DashConfig:
    url: str
    token: str


class DashError(RuntimeError):
    pass


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        key = key.strip()
        if key:
            out[key] = value.strip().strip("'").strip('"')
    return out


def _discover_dash_env() -> Path | None:
    root = secrets_dir()
    for name in ("dash.env", "argos.env"):
        path = root / name
        if path.is_file():
            return path
    home = Path.home() / ".argos" / "dash.env"
    if home.is_file():
        return home
    return None


def resolve_dash(spec: str | None) -> DashConfig:
    """Resolve dash URL + token from --dash [url|file] or env / discovered dash.env."""
    url = (os.environ.get("ARGOS_DASH_URL") or "").strip()
    token = (os.environ.get("ARGOS_TOKEN") or "").strip()
    raw = (spec or "").strip()

    if raw:
        if raw.startswith("http://") or raw.startswith("https://"):
            url = raw.rstrip("/")
        else:
            path = Path(raw).expanduser()
            if not path.is_file():
                raise DashError(
                    f"dash config not found: {path}\n"
                    "download dash.env from your dash /cli page, or pass a URL"
                )
            data = _parse_env_file(path)
            url = (data.get("ARGOS_DASH_URL") or url).strip().rstrip("/")
            token = (data.get("ARGOS_TOKEN") or token).strip()

    if not url or not token:
        discovered = _discover_dash_env()
        if discovered is not None:
            data = _parse_env_file(discovered)
            url = (data.get("ARGOS_DASH_URL") or url).strip().rstrip("/")
            token = (data.get("ARGOS_TOKEN") or token).strip()

    url = url.rstrip("/")
    if not url or not token:
        raise DashError(
            "dash requires ARGOS_DASH_URL and ARGOS_TOKEN\n"
            "download dash.env from your dash /cli page, then:\n"
            "  argos run <id> --dash ./dash.env\n"
            "or: set -a && source ./dash.env && set +a && argos run <id> --dash"
        )
    return DashConfig(url=url, token=token)


def dash_url(override: str = "") -> str:
    """Legacy helper: URL only. Prefer resolve_dash for push."""
    raw = (override or os.environ.get("ARGOS_DASH_URL") or "").strip()
    return raw.rstrip("/")


def dash_token() -> str:
    return (os.environ.get("ARGOS_TOKEN") or "").strip()


def user_agent() -> str:
    try:
        return f"argospy/{version('argospy')}"
    except PackageNotFoundError:
        return "argospy"


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
                "User-Agent": user_agent(),
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
