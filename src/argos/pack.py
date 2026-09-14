from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path

from argos.case import Result, Spec
from argos.runner import CaseFn


@dataclass
class Pack:
    id: str
    title: str
    envs: tuple[str, ...]
    apply_env: Callable[[str], str]
    load_cases: Callable[[], list[CaseFn]]
    group_order: dict[str, int] = field(default_factory=dict)
    execute: Callable[..., list[Result]] | None = None
    needs_stack: Callable[[list[CaseFn]], bool] | None = None
    stack_up: Callable[[], None] | None = None
    stack_down: Callable[[], None] | None = None
    soak_teardown: Callable[..., None] | None = None
    plan_meta: Callable[[Spec], dict] | None = None
    presets: Callable[[], list[dict]] | None = None


def load_case_modules(package: str, directory: Path) -> list[CaseFn]:
    out: list[CaseFn] = []
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        loaded = import_module(f"{package}.{path.stem}")
        if hasattr(loaded, "cases"):
            out.extend(loaded.cases())
    return out


def with_pack(spec: Spec, pack_id: str) -> Spec:
    if spec.pack == pack_id:
        return spec
    return Spec(spec.id, spec.title, spec.group, spec.tags, spec.modes, pack_id)


def stamp(cases: list[CaseFn], pack_id: str) -> list[CaseFn]:
    return [CaseFn(with_pack(case.spec, pack_id), case.fn) for case in cases]


def discover_packs() -> list[Pack]:
    group = entry_points().select(group="argos.packs")
    out: list[Pack] = []
    for ep in group:
        loaded = ep.load()
        pack = loaded() if callable(loaded) else loaded
        if not isinstance(pack, Pack):
            raise TypeError(f"entry point {ep.name} did not return a Pack")
        out.append(pack)
    out.sort(key=lambda pack: pack.id)
    return out
