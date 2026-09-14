import os
from pathlib import Path

_FILES = ("saidc-user.env", "saidc-session.env", "argos.env")


def secrets_dir() -> Path:
    env = os.environ.get("ARGOS_SECRETS")
    if env:
        return Path(env)
    here = Path.cwd().resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "secrets"
        if candidate.is_dir():
            return candidate
    return Path.home() / ".argos"


def load_secrets() -> None:
    root = secrets_dir()
    if not root.is_dir():
        return
    for name in _FILES:
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, value = raw.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip("'").strip('"')


def apply_presets(presets: dict[str, str]) -> None:
    for key, value in presets.items():
        os.environ[key] = value
