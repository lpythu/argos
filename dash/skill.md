# This Argos dash

Install this instance skill from https://<argos-host>/skill.md

```text
Install https://<argos-host>/skill.md
```

This host is a **dash instance** (run browser + ingest). It does not run cases.

## Connect the CLI

1. Log in to this dash
2. Open https://<argos-host>/cli
3. Download `dash.env` (contains `ARGOS_DASH_URL` + `ARGOS_TOKEN`)
4. On the runner machine:

```bash
argos run <id> --dash ./dash.env
# or: set -a && source ./dash.env && set +a && argos run <id> --dash
```

`--dash` prints `argos <sid>` and `dash {url}`. Acahti e2e jobs scrape that line and link `{ARGOS_DASH_URL}/runs/{sid}` from the pipeline page.

Put `dash.env` in `secrets/` (gitignored) or pass the path explicitly. Do not commit it.

## Write / run cases

Library skill (install, CLI, Context API):

```text
Install https://lpythu.github.io/argos/skill.md
```

SDK reference: https://lpythu.github.io/argos/sdk.md
