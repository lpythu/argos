---
name: argos
description: >-
  Write and run argos once/soak cases. Agent-driven: Install this skill, then
  invoke the argos CLI. Optional --dash streams to a self-hosted dash instance.
---

# argos

Install this file from https://lpythu.github.io/argos/skill.md

```text
Install https://lpythu.github.io/argos/skill.md
```

Argos is **agent-friendly**: coding agents write cases and run the CLI; humans may run the same commands locally. Do not clone the framework repo to add cases — use a pack repo with `argos.packs` entry points. SDK details: https://lpythu.github.io/argos/sdk.md

## Install

Python ≥ 3.12. Once:

```bash
pip install argospy
# plus your pack, e.g. pip install -e /path/to/argos-pack
argos list
```

Package name `argospy`, import `argos`, command `argos`. Do not use `uv run`.

## Run (local)

```bash
argos packs
argos list
argos list pack:<id>
argos run <id>
argos run <id> --env office
argos run <id> --soak --for 8h --pause 2m
```

Selectors: exact id, `pack:`, `group:`, `tag:`, `mode:once|soak`, glob. Cases tagged `e2e` require `--env`.

During / after a run: terminal progress + `out/<stamp>__<slug>/` reports — see https://lpythu.github.io/argos/local/ (or [local.md](local.md)).

## Optional: stream to dash

Dash must be deployed first (SAIDC office: https://argos.saidc.ai). On that dash, open `/cli`, download `dash.env` (`ARGOS_DASH_URL` + `ARGOS_TOKEN`). Then:

```bash
argos run <id> --dash ./dash.env
argos run <id> --dash                         # uses env / secrets/dash.env
argos run <id> --dash https://dash.example.com
argos run <id> --dash --note "office smoke"
argos push out/<stamp>__<slug> --dash ./dash.env
```

`--dash` prints `argos <sid>` (12-char public run id, no hyphens) and `dash {url}` (`{ARGOS_DASH_URL}/runs/{sid}`). In Acahti CI the CLI also records pipeline provenance (`CI_REPO`, `CI_COMMIT_SHA`, `CI_PIPELINE_NUMBER`, `CI_WORKFLOW_NAME`) so the dash run list links to the pipeline, and Acahti pipeline pages link back to that dash URL.

Dash list fields:

- **id** — `sid`, not case slug
- **selector** — the `argos run` arguments (`all`, `pack:tm`, …)
- **pack** — pack id (product e2e packs use the repo name)
- **source** — `acahti` (`owner/name #N` + actor + sha + job) or `cli` (actor)

No default dash URL. Secrets: `ARGOS_SECRETS` or `secrets/` walking up from cwd, then `~/.argos/` (`dash.env` / `argos.env`). Do not commit tokens.

Instance skill (connect only): `https://<dash>/skill.md`.

## Write a case

One file, one kind. `packs/<id>/cases/*.py` (skip `_` prefix). Export `cases() -> list[CaseFn]`. Do not add `__init__.py`.

```python
from argos.case import ONCE, SOAK, Context, Spec
from argos.runner import CaseFn

def foo(ctx: Context) -> None:
    ctx.step("place", "running")
    ctx.check(True, "unreachable")
    ctx.metric("latency_s", 1.2)
    ctx.write("probe.json", {"ok": True})
    ctx.own("resource-id", "label")
    ctx.step("place", "ok")

def cases() -> list[CaseFn]:
    return [CaseFn(Spec("foo", "short title", "live", ("e2e",), (ONCE, SOAK)), foo)]
```

`Context` (see sdk.md): `step` / `check` / `skip` / `fail` / `note` / `metric` / `sample` / `distribution` / `threshold` / `operation` / `http_operation` / `command_operation` / `write` / `own` / `fail_running`.

New product: `packs/<id>/pack.py` → `pack() -> Pack`, plus entry point `argos.packs`.

After adding: `argos list` must show the id, then `argos run <id>`.

## Rules

```text
✅ argos run <id>
✅ argos run <id> --env <name>
✅ argos run <id> --dash ./dash.env
❌ uv run argos
❌ curl + ad-hoc probes instead of a case
❌ add cases in the framework repo
❌ --push (removed; use --dash)
```
