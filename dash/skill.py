import urllib.error
import urllib.request

from config import public_url, skill_path, skill_token, skill_url

HOST = "https://<argos-host>"


def render_skill(origin: str) -> str:
    text = _load()
    return text.replace(HOST, origin.rstrip("/"))


def default_origin(request_base: str) -> str:
    configured = public_url()
    if configured:
        return configured
    return request_base.rstrip("/")


def _load() -> str:
    path = skill_path()
    if path and path.is_file():
        return path.read_text(encoding="utf-8")
    url = skill_url()
    if not url:
        raise FileNotFoundError("skill source is not configured")
    req = urllib.request.Request(url, headers={"Accept": "text/plain, text/markdown"})
    token = skill_token()
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise FileNotFoundError(str(exc.reason)) from exc
