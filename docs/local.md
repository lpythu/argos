# Local run: terminal & artifacts

Local runs need **no dash**. Progress is on the terminal; the durable result is under `out/`.

## During the run

TTY output (colors when interactive):

```text
run out/20260915-133001__demo-foo
env office  mode once  selected 1: demo:foo

[1/1] RUNNING  demo:foo  short title
    demo:foo  check:running
    demo:foo  check:ok  latency_s=1.2
    PASS   0.4s  latency_s=1.2
```

Soak adds notes like `soak iter 3` between iterations. Piped (non-TTY) output is the same text without ANSI colors.

Expect: case banners → step/metric lines → `PASS` / `FAIL` / `SKIP` → final `Results` table.

## After the run

```text
────────────────────────────────────────────────────────────────
Results
ID                               ITER STAT     TIME  METRICS
demo:foo                            1 pass     0.4s  latency_s=1.2

1 pass  0 fail  0 skip  / 1     0.5s    out/20260915-133001__demo-foo
report  out/20260915-133001__demo-foo/report.html
json    out/20260915-133001__demo-foo/report.json
md      out/20260915-133001__demo-foo/report.md
```

Directory layout:

```text
out/<stamp>__<slug>/
  report.html      # open this for the visual summary
  report.md        # same conclusion as markdown
  report.json      # machine-readable
  run.json         # run metadata (env, mode, queries, …)
  status.json      # live / final run status
  events.jsonl     # full event stream (runtime log)
  owned.json       # resources registered via ctx.own (if any)
  <case-slug>/     # per-case dir: progress.json, result.json, ctx.write files
```

| Artifact | Use |
|---|---|
| Terminal | Live progress |
| `report.html` | Human conclusion + evidence (same ReportView UI as dash) |
| `report.md` | Shareable text conclusion |
| `report.json` / `events.jsonl` | Automation / debugging |
| Case dirs | Probes, HTTP dumps, `ctx.write` outputs |

`report.html` is a self-contained shell: embedded `report.json` + the prebuilt dash ReportView (shadcn). Rebuild the viewer after UI changes: `npm run build:report` in `dash/ui` (also runs as part of `npm run build`).

Override root with `ARGOS_OUT`. Optional live mirror: `--dash ./dash.env` (still writes `out/`).
