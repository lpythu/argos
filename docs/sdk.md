# argospy SDK

Python API for writing packs and cases. Install: `pip install argospy`. Agent workflow: https://lpythu.github.io/argos/skill.md

Import package name: `argos`.

## Spec

```python
from argos.case import ONCE, SOAK, Spec

Spec(
    id="pack:case",          # unique id
    title="short title",
    group="live",
    tags=("e2e",),           # "e2e" → CLI requires --env
    modes=(ONCE, SOAK),      # default (ONCE,)
    pack="",                 # stamped by Pack loader
)
```

`ONCE` / `SOAK` are string constants `"once"` / `"soak"`.

## CaseFn

```python
from argos.runner import CaseFn

CaseFn(spec, fn)   # fn: (Context) -> None
```

Each case module exports:

```python
def cases() -> list[CaseFn]:
    return [...]
```

## Context

Created by the runner. Fields: `spec`, `dest` (case artifact dir), `run_dest`, `iteration`, `mode`.

### Control

| Method | Behavior |
|---|---|
| `step(name, status="ok", detail="")` | Record/update a step (`running` then `ok` / `failed`) |
| `check(ok, message)` | If not `ok`, raise `Fail` |
| `skip(message)` | Raise `Skip` |
| `fail(message)` | Raise `Fail` |
| `fail_running(message)` | Mark all `running` steps failed |
| `note(message)` | Attach a note / emit event |

### Metrics

| Method | Behavior |
|---|---|
| `metric(key, value, *, unit="", kind="gauge", scope="iteration")` | Scalar metric |
| `sample(name, value, *, unit="", timestamp=None, labels=None)` | Time series point (kept capped) |
| `distribution(name, values, *, unit="")` | Summary (min/avg/p50/p90/p95/p99/max) |
| `threshold(name, *, actual, operator, target, unit="")` | Record pass/fail; operators `>=` `>` `<=` `<` `==`; returns bool |

### Evidence

| Method | Behavior |
|---|---|
| `operation(label, *, kind, operation, expected, actual, artifacts=None, step_name="")` | Attach evidence to active/`step_name` step |
| `http_operation(label, method, url, *, request, status, body, expected_status, artifact="", step_name="")` | HTTP evidence |
| `command_operation(label, command, *, returncode, stdout="", stderr="", expected_returncode=0, artifact="", step_name="", elapsed_s=None)` | Command evidence (redacts secrets) |

Requires an active step (usually `step(..., "running")` first).

### Artifacts / ownership

| Method | Behavior |
|---|---|
| `write(name, obj)` | Write under `ctx.dest` (bytes/str/JSON) |
| `own(resource_id, catalog_id="")` | Register resource id in run `owned.json` |

## Pack

```python
from pathlib import Path
from argos.pack import Pack, load_case_modules, stamp

def pack() -> Pack:
    return Pack(
        id="demo",
        title="Demo pack",
        envs=("office", "bj-test"),
        apply_env=_apply_env,          # (name: str) -> str
        load_cases=_load,              # () -> list[CaseFn]
        # optional:
        # group_order={}, execute=..., needs_stack=..., stack_up=...,
        # stack_down=..., soak_teardown=..., plan_meta=..., presets=...,
    )
```

Discover cases:

```python
def _load() -> list[CaseFn]:
    return stamp(
        load_case_modules("mypack.cases", Path(__file__).parent / "cases"),
        "demo",
    )
```

Register in `pyproject.toml`:

```toml
[project.entry-points."argos.packs"]
demo = "mypack.pack:pack"
```

## CLI (library surface)

| Command | Notes |
|---|---|
| `argos packs` / `argos list` | Discover |
| `argos run <query…>` | Local run |
| `argos run … --dash [url\|file]` | Stream to dash |
| `argos push <out-dir> --dash …` | Upload finished dir |
| `argos dash [url\|file]` | Open configured dash |
| `argos up` / `argos down` | Pack local stack |

`--dash` with no value uses `ARGOS_DASH_URL` + `ARGOS_TOKEN` or discovered `secrets/dash.env`. Path argument loads both keys from that file. URL argument sets origin; token still from env/file. HTTP shape: https://lpythu.github.io/argos/ingest/

Terminal progress and `out/` layout: https://lpythu.github.io/argos/local/

## Exceptions

- `argos.case.Skip` — skipped result  
- `argos.case.Fail` — failed result (`check` / `fail`)
