---
name: argos
description: >-
  Write and run argos once/soak cases in this repo. Use when adding or changing
  cases, orchestrating soak, or verifying a product stack instead of ad-hoc
  curl/pytest/probes.
---

# argos

Install this file from https://<argos-host>/skill.md

```text
Install https://<argos-host>/skill.md
```

Do not clone the argos framework repo. This pack repo is the only place to add cases.

## Install

Python ≥ 3.12. Once:

```bash
git clone https://acahti.saidc.ai/saidc/argos-pack.git
cd argos-pack
pip install -e .
```

`pip install -e .` installs `argospy` from PyPI and puts `argos` on PATH. Do not clone the framework repo. Do not use `uv run`.

## Run

```bash
argos packs
argos list
argos list pack:tm
argos run <id>
argos run <id> --env office
argos run <id> --soak --for 8h --pause 2m
argos run pack:tm --env office --push
argos push out/<stamp>__<slug>
argos dash
```

Selectors: exact id, `pack:`, `group:`, `tag:`, `mode:once|soak`, glob. Cases tagged `e2e` require `--env`. Output: `./out/<stamp>__<slug>/` (or `ARGOS_OUT`).

`--push` streams status to dash so others can log in and see it. Needs `ARGOS_TOKEN`. Default dash is `https://argos.saidc.ai` (`ARGOS_DASH_URL` / `--dash` to point at the host you deployed).

Secrets: `ARGOS_SECRETS` or a `secrets/` directory walking up from cwd, then `~/.argos/`. Put `ARGOS_TOKEN` in `secrets/argos.env`.

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

`Context`: `step` / `check` / `skip` / `fail` / `note` / `metric` / `write` / `own`. New product: `packs/<id>/pack.py` exporting `pack() -> Pack`, plus an entry point in `pyproject.toml` under `argos.packs`.

After adding: `argos list` must show the id, then `argos run <id>`.
