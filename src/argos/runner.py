import json
import os
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from argos.case import ONCE, Context, Fail, Result, Skip, Spec


class CaseFn:
    def __init__(self, spec: Spec, fn: Callable):
        self.spec = spec
        self.fn = fn


def case_folder(spec: Spec, iteration: int = 0) -> str:
    folder = spec.slug
    if iteration:
        folder = f"{folder}__{iteration:04d}"
    return folder


def run_one(
    case: CaseFn,
    dest: Path,
    emit: Callable[[dict], None],
    iteration: int = 0,
    *,
    mode: str = ONCE,
) -> Result:
    ctx = Context(
        case.spec,
        dest / case_folder(case.spec, iteration),
        emit,
        iteration=iteration,
        run_dest=dest,
        mode=mode,
    )
    emit({"type": "start", "id": case.spec.id, "iteration": iteration})
    started = time.time()
    status = "pass"
    error = ""
    try:
        case.fn(ctx)
    except Skip as exc:
        status = "skip"
        error = str(exc)
    except Fail as exc:
        status = "fail"
        error = str(exc)
    except Exception as exc:
        status = "fail"
        error = str(exc)
        ctx.write("traceback.txt", traceback.format_exc())
    elapsed = time.time() - started
    result = Result(
        spec=case.spec,
        status=status,
        elapsed_s=elapsed,
        error=error,
        metrics=dict(ctx.metrics),
        steps=list(ctx.steps),
        notes=list(ctx.notes),
        dest=str(ctx.dest),
        iteration=iteration,
    )
    ctx.write(
        "result.json",
        {
            "id": case.spec.id,
            "slug": case.spec.slug,
            "title": case.spec.title,
            "group": case.spec.group,
            "iteration": iteration,
            "status": status,
            "elapsed_s": round(elapsed, 3),
            "error": error,
            "metrics": result.metrics,
            "steps": [s.__dict__ for s in result.steps],
            "notes": result.notes,
        },
    )
    emit({"type": "end", "id": case.spec.id, "result": result})
    return result


class GPUBudget:
    def __init__(self, total: int):
        self.total = max(0, total)
        self.free = self.total
        self._cv = threading.Condition()

    def acquire(self, n: int) -> None:
        if n <= 0:
            return
        with self._cv:
            while self.free < n:
                self._cv.wait()
            self.free -= n

    def release(self, n: int) -> None:
        if n <= 0:
            return
        with self._cv:
            self.free += n
            self._cv.notify_all()

    def snapshot(self) -> int:
        with self._cv:
            return self.free


def run_packed(
    cases: list[CaseFn],
    dest: Path,
    emit: Callable[[dict], None],
    slots_of: Callable[[CaseFn], int],
    budget: GPUBudget,
    iteration: int = 0,
    mode: str = ONCE,
) -> list[Result]:
    results: list[Result | None] = [None] * len(cases)
    workers = max(1, min(len(cases), int(os.environ.get("ARGOS_MAX_PARALLEL", "16"))))

    def work(index: int, case: CaseFn) -> None:
        need = slots_of(case)
        emit({"type": "pack", "id": case.spec.id, "slots": need, "action": "wait", "free": budget.snapshot()})
        budget.acquire(need)
        emit({"type": "pack", "id": case.spec.id, "slots": need, "action": "run", "free": budget.snapshot()})
        try:
            results[index] = run_one(case, dest, emit, iteration, mode=mode)
        finally:
            budget.release(need)
            emit({"type": "pack", "id": case.spec.id, "slots": need, "action": "done", "free": budget.snapshot()})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(work, i, case) for i, case in enumerate(cases)]
        for fut in futs:
            fut.result()
    return [r for r in results if r is not None]


def write_events(path: Path, event: dict) -> None:
    row = {k: v for k, v in event.items() if k != "result"}
    if "result" in event:
        result: Result = event["result"]
        row["status"] = result.status
        row["elapsed_s"] = result.elapsed_s
        row["error"] = result.error
        row["iteration"] = result.iteration
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
