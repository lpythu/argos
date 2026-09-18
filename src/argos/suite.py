from collections import OrderedDict
from pathlib import Path
from typing import Callable

from argos.case import ONCE, Result, Spec
from argos.pack import Pack, discover_packs, stamp
from argos.run_status import StopRequested
from argos.runner import CaseFn, run_one

_PACKS: list[Pack] | None = None

# Aliyun public stack: bj-test replaced hk. Accept either name so
# already-tagged CD (`--env bj-test`) still applies packs that only list hk.
_ENV_ALIASES = {"bj-test": "hk", "hk": "bj-test"}


def all_packs() -> list[Pack]:
    global _PACKS
    if _PACKS is None:
        _PACKS = discover_packs()
    return _PACKS


def pack_named(pack_id: str) -> Pack | None:
    for pack in all_packs():
        if pack.id == pack_id:
            return pack
    return None


def env_names() -> tuple[str, ...]:
    seen: list[str] = []
    for pack in all_packs():
        for name in pack.envs:
            if name not in seen:
                seen.append(name)
    for name, alias in _ENV_ALIASES.items():
        if name in seen and alias not in seen:
            seen.append(alias)
    return tuple(seen)


def apply_env(name: str, packs: list[Pack] | None = None) -> str:
    env = (name or "").strip().lower()
    targets = packs if packs is not None else all_packs()
    matched = [pack for pack in targets if env in pack.envs]
    if not matched:
        alias = _ENV_ALIASES.get(env)
        if alias:
            matched = [pack for pack in targets if alias in pack.envs]
            if matched:
                env = alias
    if not matched:
        allowed = ", ".join(env_names()) or "(none)"
        raise ValueError(f"unknown env {name!r}; use {allowed}")
    for pack in matched:
        pack.apply_env(env)
    return env


def all_cases() -> list[CaseFn]:
    out: list[CaseFn] = []
    for pack in all_packs():
        out.extend(stamp(pack.load_cases(), pack.id))
    def _order(case: CaseFn) -> tuple[str, int, str]:
        pack = pack_named(case.spec.pack)
        group_n = pack.group_order.get(case.spec.group, 9) if pack else 9
        return (case.spec.pack, group_n, case.spec.id)

    out.sort(key=_order)
    return out


def packs_of(cases: list[CaseFn]) -> list[Pack]:
    seen: OrderedDict[str, Pack] = OrderedDict()
    for case in cases:
        pack = pack_named(case.spec.pack)
        if pack and pack.id not in seen:
            seen[pack.id] = pack
    return list(seen.values())


def execute(
    chosen: list[CaseFn], dest: Path, emit: Callable[[dict], None], iteration: int = 0, *, mode: str = ONCE
) -> list[Result]:
    grouped: OrderedDict[str, list[CaseFn]] = OrderedDict()
    for case in chosen:
        grouped.setdefault(case.spec.pack, []).append(case)
    results: list[Result] = []
    try:
        for pack_id, cases in grouped.items():
            pack = pack_named(pack_id)
            if pack and pack.execute:
                results.extend(pack.execute(cases, dest, emit, iteration, mode=mode))
                continue
            for case in cases:
                results.append(run_one(case, dest, emit, iteration, mode=mode))
    except StopRequested as exc:
        exc.results = [*results, *exc.results]
        raise
    return results


def plan_meta(spec: Spec) -> dict:
    pack = pack_named(spec.pack)
    if pack and pack.plan_meta:
        return pack.plan_meta(spec)
    return {"hint": spec.title, "typical_s": 120, "mutex": ""}


def all_presets() -> list[dict]:
    out: list[dict] = []
    for pack in all_packs():
        if pack.presets:
            out.extend(pack.presets())
    return out
