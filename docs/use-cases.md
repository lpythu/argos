# Use cases

## Preview before commit

Run Skheri's Vite example, then use the public argos-pack `web:preview` case with
ARGOS_BASE_URL set to its port-forward or authenticated preview endpoint. Record
the expected text, test the edited page, and attach the run report to the task.
A successful run describes the observed page; record its source revision or
snapshot before treating it as release evidence.

## Verify a deployed API

Create a pack that checks health and a representative business operation with
synthetic data. Select the target explicitly with --env. Fail when required
configuration is missing. CI should archive report.json and report.html alongside
the commit SHA and deployed image digest.

## Observe stability

Run the same case in soak mode with a bounded duration and pause. Assert response
and latency requirements, record metrics, and inspect failures over time. This
checks the sampled behavior; it is not a load generator or an availability guarantee.

## Team evidence

Keep local-only execution for quick checks. Add Argos Dash when a team needs a
shared run browser. Credentials live in an untracked connection file; test code
and report contracts stay independent of that dashboard installation.

Runnable examples: https://github.com/benchyard/argos-pack
