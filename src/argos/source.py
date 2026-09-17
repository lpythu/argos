import getpass
import os
from typing import Any


def _env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _local_actor() -> str:
    actor = _env("ARGOS_ACTOR", "USER", "LOGNAME")
    if actor:
        return actor
    try:
        return (getpass.getuser() or "").strip()
    except Exception:
        return ""


def run_source(*, note: str = "") -> dict[str, Any]:
    note = (note or os.environ.get("ARGOS_NOTE") or "").strip()
    ci = (os.environ.get("CI") or "").strip().lower()
    root = (os.environ.get("ACAHTI_ROOT_URL") or "").strip().rstrip("/")
    if ci == "woodpecker" or root:
        repo = (os.environ.get("CI_REPO") or "").strip()
        number = (os.environ.get("CI_PIPELINE_NUMBER") or "").strip()
        url = f"{root}/repos/{repo}/pipelines/{number}" if root and repo and number else ""
        ref = (
            os.environ.get("CI_COMMIT_TAG")
            or os.environ.get("CI_COMMIT_BRANCH")
            or os.environ.get("CI_COMMIT_REF")
            or ""
        ).strip()
        pipeline: int | None = int(number) if number.isdigit() else None
        return {
            "kind": "acahti",
            "repo": repo,
            "sha": (os.environ.get("CI_COMMIT_SHA") or "").strip(),
            "ref": ref,
            "pipeline": pipeline,
            "job": (os.environ.get("CI_WORKFLOW_NAME") or "").strip(),
            "step": (os.environ.get("CI_STEP_NAME") or "").strip(),
            "url": url,
            "actor": _env("ACAHTI_USER", "CI_COMMIT_AUTHOR") or _local_actor(),
            "note": note,
        }
    return {"kind": "cli", "note": note, "actor": _local_actor()}
