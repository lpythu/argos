import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ONCE = "once"
SOAK = "soak"


def case_slug(case_id: str) -> str:
    return case_id.replace(":", "-")


def run_slug(ids: list[str]) -> str:
    if not ids:
        return "empty"
    if len(ids) == 1:
        return case_slug(ids[0])
    groups = {part.split(":", 1)[0] if ":" in part else part for part in ids}
    if len(groups) == 1:
        return next(iter(groups))
    if len(ids) <= 3:
        return "+".join(case_slug(i) for i in ids)
    return f"{len(ids)}-cases"


@dataclass(frozen=True)
class Spec:
    id: str
    title: str
    group: str
    tags: tuple[str, ...] = ()
    modes: tuple[str, ...] = (ONCE,)
    pack: str = ""

    @property
    def slug(self) -> str:
        return case_slug(self.id)


@dataclass
class Step:
    name: str
    status: str
    detail: str = ""


@dataclass
class Result:
    spec: Spec
    status: str
    elapsed_s: float
    error: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dest: str = ""
    iteration: int = 0


class Skip(Exception):
    pass


class Fail(Exception):
    pass


class Context:
    def __init__(
        self,
        spec: Spec,
        dest: Path,
        emit: Callable[[dict], None],
        *,
        iteration: int = 0,
        run_dest: Path | None = None,
        mode: str = ONCE,
    ):
        self.spec = spec
        self.dest = dest
        self.dest.mkdir(parents=True, exist_ok=True)
        self.iteration = iteration
        self.run_dest = run_dest or dest.parent
        self.mode = mode
        self.metrics: dict[str, Any] = {}
        self.steps: list[Step] = []
        self.notes: list[str] = []
        self._emit = emit
        self.write(
            "case.json",
            {
                "id": spec.id,
                "slug": spec.slug,
                "title": spec.title,
                "group": spec.group,
                "pack": spec.pack,
                "tags": list(spec.tags),
                "modes": list(spec.modes),
            },
        )

    def metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value
        self._dump()
        self._emit({"type": "metric", "id": self.spec.id, "key": key, "value": value})

    def note(self, message: str) -> None:
        self.notes.append(message)
        self._emit({"type": "note", "id": self.spec.id, "message": message})

    def step(self, name: str, status: str = "ok", detail: str = "") -> None:
        row = Step(name=name, status=status, detail=detail)
        for i, existing in enumerate(self.steps):
            if existing.name == name:
                self.steps[i] = row
                break
        else:
            self.steps.append(row)
        self._dump()
        self._emit({"type": "step", "id": self.spec.id, "name": name, "status": status, "detail": detail})

    def check(self, ok: bool, message: str) -> None:
        if not ok:
            raise Fail(message)

    def skip(self, message: str) -> None:
        raise Skip(message)

    def fail(self, message: str) -> None:
        raise Fail(message)

    def own(self, resource_id: str, catalog_id: str = "") -> None:
        path = self.run_dest / "owned.json"
        rows: list[dict[str, str]] = []
        if path.exists():
            raw = json.loads(path.read_text())
            if isinstance(raw, list):
                rows = [row for row in raw if isinstance(row, dict)]
        if any(row.get("id") == resource_id for row in rows):
            return
        rows.append({"id": resource_id, "catalog_id": catalog_id})
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")

    def write(self, name: str, obj: Any) -> Path:
        path = self.dest / name
        if isinstance(obj, (bytes, bytearray)):
            path.write_bytes(obj)
        elif isinstance(obj, str):
            path.write_text(obj)
        else:
            path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
        return path

    def _dump(self) -> None:
        self.write(
            "progress.json",
            {
                "id": self.spec.id,
                "slug": self.spec.slug,
                "title": self.spec.title,
                "metrics": self.metrics,
                "steps": [s.__dict__ for s in self.steps],
                "notes": self.notes,
            },
        )
