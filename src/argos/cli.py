import argparse
import json
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from argos.case import ONCE, SOAK, run_slug
from argos.client import Client, DashError, resolve_dash, push_dir
from argos.duration import parse_duration
from argos.paths import out_root
from argos.report import write_reports
from argos.run_status import RunStatus, StopRequested
from argos.runner import public_event, write_events
from argos.secrets import load_secrets
from argos.select import select
from argos.source import run_source
from argos.suite import all_cases, all_packs, apply_env, env_names, execute, pack_named, packs_of
from argos.term import DIM, RESET, Progress, fmt_dur


def list_packs() -> int:
    packs = all_packs()
    print(f"{'ID':<16} {'ENVS':<24} TITLE")
    for pack in packs:
        print(f"{pack.id:<16} {','.join(pack.envs):<24} {pack.title}")
    print(f"\n{len(packs)} packs")
    return 0


def list_cases(queries: list[str], mode: str | None) -> int:
    catalog = all_cases()
    specs = select([c.spec for c in catalog], queries)
    if mode:
        specs = [s for s in specs if mode in s.modes]
    print(f"{'ID':<32} {'PACK':<10} {'SLUG':<28} {'GROUP':<10} {'MODES':<12} {'TAGS':<22} TITLE")
    for spec in specs:
        tags = ",".join(spec.tags)
        modes = ",".join(spec.modes)
        print(f"{spec.id:<32} {spec.pack:<10} {spec.slug:<28} {spec.group:<10} {modes:<12} {tags:<22} {spec.title}")
    print(f"\n{len(specs)} cases")
    print()
    print("once   argos run <id>")
    print("soak   argos run <id> --soak --for 8h")
    print("env    argos run <id> --env <name>")
    print("pack   argos list pack:<id>")
    print("dash   argos run <id> --dash ./dash.env")
    return 0


def _env_help() -> str:
    names = env_names()
    if not names:
        return "named environment from the selected packs"
    return "e2e target: " + " / ".join(names)


def _resolve_stack_pack(pack_id: str | None):
    candidates = [pack for pack in all_packs() if pack.stack_up]
    if pack_id:
        pack = pack_named(pack_id)
        if not pack:
            raise RuntimeError(f"unknown pack {pack_id}")
        if not pack.stack_up:
            raise RuntimeError(f"pack {pack_id} has no stack")
        return pack
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise RuntimeError("no pack defines a stack")
    names = " ".join(pack.id for pack in candidates)
    raise RuntimeError(f"choose a pack: argos up <{names}>")


def run_cases(
    queries: list[str],
    *,
    soak: bool,
    duration: str,
    pause: str,
    fail_fast: bool,
    env: str | None,
    dash: str | None,
    note: str = "",
) -> int:
    if not queries:
        print("select at least one case. examples:", file=sys.stderr)
        print("  argos list", file=sys.stderr)
        print("  argos list pack:<id>", file=sys.stderr)
        print("  argos run unit", file=sys.stderr)
        return 2
    catalog = all_cases()
    picked = select([c.spec for c in catalog], queries)
    if not picked:
        print("no cases matched", " ".join(queries), file=sys.stderr)
        return 2
    by_id = {c.spec.id: c for c in catalog}
    chosen = [by_id[s.id] for s in picked]
    mode = SOAK if soak else ONCE
    unsupported = [c.spec.id for c in chosen if mode not in c.spec.modes]
    if unsupported:
        print(f"{mode} not supported:", ", ".join(unsupported), file=sys.stderr)
        print("see: argos list", file=sys.stderr)
        return 2
    involved = packs_of(chosen)
    has_e2e = any("e2e" in c.spec.tags for c in chosen)
    if has_e2e and not env:
        names = [name for pack in involved for name in pack.envs]
        seen: list[str] = []
        for name in names:
            if name not in seen:
                seen.append(name)
        print("e2e cases require --env " + (" or ".join(seen) if seen else "<pack env>"), file=sys.stderr)
        return 2
    if env:
        try:
            applied = apply_env(env, involved)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    else:
        applied = ""

    stamp = time.strftime("%Y%m%d-%H%M%S")
    slug = run_slug([c.spec.id for c in chosen])
    dest = out_root() / f"{stamp}__{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    run_meta = {
        "started": stamp,
        "slug": slug,
        "mode": mode,
        "env": applied,
        "duration": duration if soak else "",
        "pause": pause if soak else "",
        "fail_fast": bool(fail_fast and soak),
        "packs": [{"id": pack.id, "title": pack.title} for pack in involved],
        "queries": queries,
        "runner": socket.gethostname(),
        "source": run_source(note=note),
        "cases": [
            {
                "id": c.spec.id,
                "slug": c.spec.slug,
                "title": c.spec.title,
                "group": c.spec.group,
                "pack": c.spec.pack,
            }
            for c in chosen
        ],
    }
    dest.joinpath("run.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n")
    if len(chosen) == 1:
        plan_title = chosen[0].spec.title
    elif len(involved) == 1:
        plan_title = f"{involved[0].title} · {len(chosen)} cases"
    else:
        plan_title = f"{len(chosen)} cases"
    if soak:
        plan_title += f" · soak {duration}"
    run_status = RunStatus(
        dest,
        [case.spec for case in chosen],
        title=plan_title,
        mode=mode,
        env=applied,
        duration=duration if soak else "",
    )
    events = dest / "events.jsonl"
    progress = Progress([c.spec for c in chosen], str(dest))
    lock = threading.Lock()
    remote: Client | None = None
    remote_id = ""
    pending: list[dict] = []

    if dash is not None:
        try:
            cfg = resolve_dash(dash)
        except DashError as exc:
            print(exc, file=sys.stderr)
            return 2
        remote = Client(cfg.url, cfg.token)
        try:
            created = remote.create_run(run_meta)
        except DashError as exc:
            print(exc, file=sys.stderr)
            return 2
        remote_id = str(created.get("sid") or created.get("id") or "")
        print(f"argos {remote_id}")
        print(f"dash {created.get('url') or remote.browse_url(remote_id)}")

    def flush_remote() -> None:
        if not remote or not remote_id or not pending:
            return
        batch = pending[:]
        pending.clear()
        remote.post_events(remote_id, batch)

    def emit(event: dict) -> None:
        with lock:
            write_events(events, event)
            run_status.on_event(event)
            progress.on_event(event)
            if remote and remote_id:
                pending.append(public_event(event))
                if len(pending) >= 20:
                    try:
                        flush_remote()
                    except DashError as exc:
                        print(exc, file=sys.stderr)

    print(f"run {dest}")
    print(f"env {applied or '-'}  mode {mode}  selected {len(chosen)}: " + " ".join(c.spec.id for c in chosen))
    for pack in involved:
        pack_cases = [c for c in chosen if c.spec.pack == pack.id]
        if pack.needs_stack and pack.needs_stack(pack_cases):
            try:
                pack.stack_up()
            except RuntimeError as exc:
                run_status.finish("fail", str(exc))
                print(exc, file=sys.stderr)
                return 2
    started = time.time()
    results = []
    interrupted = False
    try:
        if not soak:
            results = execute(chosen, dest, emit, iteration=0, mode=mode)
        else:
            budget = parse_duration(duration)
            gap = 0.0 if pause in {"", "0", "0s"} else parse_duration(pause)
            deadline = started + budget
            print(f"soak {fmt_dur(budget).strip()}  pause {fmt_dur(gap).strip()}  fail_fast={fail_fast}")
            n = 0
            while time.time() < deadline + run_status.paused_seconds:
                if run_status.stop_requested():
                    interrupted = True
                    break
                n += 1
                left = deadline + run_status.paused_seconds - time.time()
                emit({"type": "note", "id": chosen[0].spec.id, "message": f"soak iter {n}  left {fmt_dur(left).strip()}"})
                batch = execute(chosen, dest, emit, iteration=n, mode=mode)
                results.extend(batch)
                if run_status.stop_requested():
                    interrupted = True
                    break
                if fail_fast and any(r.status == "fail" for r in batch):
                    break
                if time.time() + gap >= deadline + run_status.paused_seconds:
                    break
                if gap > 0:
                    time.sleep(gap)
    except StopRequested as exc:
        results.extend(exc.results)
        interrupted = True
    except KeyboardInterrupt:
        interrupted = True
        print("interrupted", file=sys.stderr)
    if soak:
        for pack in involved:
            if pack.soak_teardown:
                pack.soak_teardown(dest, emit, [c for c in chosen if c.spec.pack == pack.id])
    write_reports(dest, results, stamp, wall_s=time.time() - started)
    failed = next((result for result in results if result.status == "fail"), None)
    final = "interrupted" if interrupted else "fail" if failed or not results else "pass"
    run_status.finish(final, failed.error if failed else "")
    progress.summary()
    print(f"report  {dest / 'report.html'}")
    print(f"json    {dest / 'report.json'}")
    print(f"md      {dest / 'report.md'}")
    if remote and remote_id:
        try:
            with lock:
                flush_remote()
            report = json.loads((dest / "report.json").read_text())
            remote.finish(remote_id, report, final)
            print(f"argos {remote_id}")
            print(f"dash {remote.browse_url(remote_id)}")
        except DashError as exc:
            print(exc, file=sys.stderr)
    if sys.stdout.isatty():
        print(f"{DIM}open the HTML report for the visual summary{RESET}")
    if interrupted:
        return 130
    return 0 if results and all(r.status != "fail" for r in results) else 1


def cmd_push(path: str, dash: str | None) -> int:
    dest = Path(path)
    if not dest.is_dir():
        print(f"not a run directory: {dest}", file=sys.stderr)
        return 2
    try:
        cfg = resolve_dash(dash if dash is not None else "")
    except DashError as exc:
        print(exc, file=sys.stderr)
        return 2
    client = Client(cfg.url, cfg.token)
    try:
        run_id = push_dir(client, dest)
    except DashError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"argos {run_id}")
    print(f"dash {client.browse_url(run_id)}")
    return 0


def cmd_dash(target: str | None, no_open: bool) -> int:
    try:
        cfg = resolve_dash(target if target is not None else "")
    except DashError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(cfg.url)
    if not no_open:
        webbrowser.open(cfg.url)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_secrets()
    parser = argparse.ArgumentParser(prog="argos", description="once / soak test framework")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("packs", help="list installed packs")
    p_list = sub.add_parser("list", help="list cases and how to run them")
    p_list.add_argument("query", nargs="*", help="id, pack:, group:, tag:, mode:once|soak, or glob")
    p_list.add_argument("--mode", choices=(ONCE, SOAK), help="only cases that support this mode")
    p_run = sub.add_parser("run", help="run selected cases once, or soak until --for")
    p_run.add_argument("query", nargs="*", help="id, pack:, group:, tag:, mode:, or glob")
    p_run.add_argument("--soak", action="store_true", help="repeat until --for (k6-style constant duration)")
    p_run.add_argument("--for", dest="duration", default="8h", help="soak budget (8h, 90m, 1h30m). default 8h")
    p_run.add_argument("--pause", default="0s", help="sleep between soak iterations")
    p_run.add_argument("--fail-fast", action="store_true", help="stop soak on first failed iteration")
    p_run.add_argument("--env", choices=env_names() or None, help=_env_help())
    p_run.add_argument(
        "--dash",
        nargs="?",
        const="",
        default=None,
        metavar="URL|FILE",
        help="stream to dash: bare --dash, URL, or dash.env path",
    )
    p_run.add_argument("--note", default="", help="optional remark stored on the dash run")
    p_up = sub.add_parser("up", help="start a pack's local stack")
    p_up.add_argument("pack", nargs="?", help="pack id (default: the only pack that has a stack)")
    p_down = sub.add_parser("down", help="stop a pack's local stack")
    p_down.add_argument("pack", nargs="?", help="pack id (default: the only pack that has a stack)")
    p_push = sub.add_parser("push", help="upload a finished local run directory")
    p_push.add_argument("path", help="out/<stamp>__<slug> directory")
    p_push.add_argument(
        "--dash",
        nargs="?",
        const="",
        default="",
        metavar="URL|FILE",
        help="dash URL or dash.env (default: env / discovered secrets)",
    )
    p_dash = sub.add_parser("dash", help="open the configured dash")
    p_dash.add_argument(
        "target",
        nargs="?",
        default=None,
        help="dash URL or dash.env (default: env / discovered secrets)",
    )
    p_dash.add_argument("--no-open", action="store_true", help="print the URL only")
    args = parser.parse_args(argv)
    if args.cmd == "packs":
        return list_packs()
    if args.cmd == "list":
        return list_cases(args.query, args.mode)
    if args.cmd == "push":
        return cmd_push(args.path, args.dash)
    if args.cmd == "dash":
        return cmd_dash(args.target, args.no_open)
    if args.cmd in {"up", "down"}:
        try:
            pack = _resolve_stack_pack(args.pack)
            if pack.envs:
                apply_env(pack.envs[0], [pack])
            if args.cmd == "up":
                pack.stack_up()
            else:
                if not pack.stack_down:
                    raise RuntimeError(f"pack {pack.id} has no stack down")
                pack.stack_down()
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0
    return run_cases(
        args.query,
        soak=args.soak,
        duration=args.duration,
        pause=args.pause,
        fail_fast=args.fail_fast,
        env=args.env,
        dash=args.dash,
        note=args.note,
    )


if __name__ == "__main__":
    raise SystemExit(main())
