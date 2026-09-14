import fnmatch

from argos.case import Spec


def matches(spec: Spec, query: str) -> bool:
    q = query.strip()
    if not q or q in {"all", "*"}:
        return True
    if q.startswith("pack:"):
        return spec.pack == q.split(":", 1)[1]
    if q.startswith("group:"):
        return spec.group == q.split(":", 1)[1]
    if q.startswith("tag:"):
        return q.split(":", 1)[1] in spec.tags
    if q.startswith("mode:"):
        return q.split(":", 1)[1] in spec.modes
    if any(ch in q for ch in "*?[]"):
        return fnmatch.fnmatch(spec.id, q)
    return (
        spec.id == q
        or spec.id.startswith(q + ":")
        or spec.group == q
        or spec.pack == q
        or q in spec.tags
        or q in spec.modes
    )


def select(specs: list[Spec], queries: list[str]) -> list[Spec]:
    if not queries:
        return list(specs)
    return [spec for spec in specs if all(matches(spec, query) for query in queries)]
