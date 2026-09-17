import os
from typing import Any


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
        out: dict[str, Any] = {
            "kind": "acahti",
            "repo": repo,
            "sha": (os.environ.get("CI_COMMIT_SHA") or "").strip(),
            "ref": ref,
            "pipeline": pipeline,
            "job": (os.environ.get("CI_WORKFLOW_NAME") or "").strip(),
            "step": (os.environ.get("CI_STEP_NAME") or "").strip(),
            "url": url,
            "actor": (os.environ.get("CI_COMMIT_AUTHOR") or os.environ.get("ACAHTI_USER") or "").strip(),
            "note": note,
        }
        return out
    return {"kind": "cli", "note": note}
