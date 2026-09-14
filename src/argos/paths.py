import os
from pathlib import Path


def out_root() -> Path:
    env = os.environ.get("ARGOS_OUT")
    if env:
        return Path(env)
    return Path.cwd() / "out"
