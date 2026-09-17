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


def peek_dash_url(spec: str | None = None) -> str:
    """Dash origin for the report template. Empty if none is configured. No token."""
    url = (os.environ.get("ARGOS_DASH_URL") or "").strip()
    raw = (spec or "").strip()
    if raw:
        if raw.startswith("http://") or raw.startswith("https://"):
            url = raw.rstrip("/")
        else:
            path = Path(raw).expanduser()
            if path.is_file():
                data = _parse_env_file(path)
                url = (data.get("ARGOS_DASH_URL") or url).strip().rstrip("/")
    if not url:
        discovered = _discover_dash_env()
        if discovered is not None:
            data = _parse_env_file(discovered)
            url = (data.get("ARGOS_DASH_URL") or url).strip().rstrip("/")
    return url.rstrip("/")


INGEST_VERSION = "1"


def _view_cache_dir() -> Path:
    return Path.home() / ".argos" / "report-view" / INGEST_VERSION


def _read_view_cache() -> tuple[str, str] | None:
    root = _view_cache_dir()
    css_path, js_path = root / "viewer.css", root / "viewer.js"
    if css_path.is_file() and js_path.is_file():
        return css_path.read_text(encoding="utf-8"), js_path.read_text(encoding="utf-8")
    return None


def _write_view_cache(css: str, js: str) -> None:
    root = _view_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "viewer.css").write_text(css, encoding="utf-8")
    (root / "viewer.js").write_text(js, encoding="utf-8")


def _http_get(url: str, etag: str = "") -> tuple[int, bytes, str]:
    headers = {"User-Agent": user_agent(), "Accept": "*/*"}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(resp.status), resp.read(), str(resp.headers.get("ETag") or "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        tag = str(exc.headers.get("ETag") or "") if exc.headers else ""
        return int(exc.code), body, tag


def _fetch_asset(origin: str, name: str) -> str | None:
    root = _view_cache_dir()
    path = root / name
    etag_path = root / f"{name}.etag"
    etag = etag_path.read_text(encoding="utf-8").strip() if etag_path.is_file() else ""
    code, body, new_etag = _http_get(f"{origin}/report-view/{name}", etag)
    if code == 304 and path.is_file():
        return path.read_text(encoding="utf-8")
    if code != 200 or not body:
        return None
    text = body.decode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if new_etag:
        etag_path.write_text(new_etag, encoding="utf-8")
    return text


def load_report_view(spec: str | None = None) -> tuple[str, str] | None:
    """CSS + JS for local report.html. Cache under ~/.argos/report-view/<ingest>/."""
    cached = _read_view_cache()
    origin = peek_dash_url(spec)
    if not origin:
        return cached
    try:
        code, body, _ = _http_get(f"{origin}/report-view/manifest.json")
        if code != 200 or not body:
            return cached
        manifest = json.loads(body.decode("utf-8"))
        if not isinstance(manifest, dict) or str(manifest.get("ingest") or "") != INGEST_VERSION:
            return cached
        css = _fetch_asset(origin, "viewer.css")
        js = _fetch_asset(origin, "viewer.js")
        if css is None or js is None:
            return cached
        _write_view_cache(css, js)
        return css, js
    except Exception:
        return cached


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
                "X-Argos-Ingest": INGEST_VERSION,
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
    run_id = str(created.get("sid") or created["id"])
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
