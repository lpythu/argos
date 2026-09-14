import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import analyze
from auth import current_user, require_ingest
from config import data_root, public_url
from database import get_db
from models import CaseRow, Run, User

router = APIRouter()


class RunCreate(BaseModel):
    stamp: str = ""
    slug: str = ""
    mode: str = "once"
    env: str = ""
    queries: list[str] = Field(default_factory=list)
    packs: list[str] = Field(default_factory=list)
    runner: str = ""
    cases: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "running"


class EventsBody(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)


class FinishBody(BaseModel):
    report: dict[str, Any] = Field(default_factory=dict)
    status: str = "pass"


class FileBody(BaseModel):
    path: str
    text: str


def _run_dir(run_id: UUID) -> Path:
    dest = data_root() / "runs" / str(run_id)
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _dump(run: Run, *, detail: bool = False) -> dict[str, Any]:
    stats = analyze.counts(run)
    data = {
        "id": str(run.id),
        "url": f"{public_url()}/runs/{run.id}",
        "stamp": run.stamp,
        "slug": run.slug,
        "mode": run.mode,
        "env": run.env,
        "status": run.status,
        "runner": run.runner,
        "queries": run.queries,
        "packs": run.packs,
        "summary": run.summary,
        "created_at": run.created_at.isoformat() if run.created_at else "",
        "finished_at": run.finished_at.isoformat() if run.finished_at else "",
        "elapsed_s": analyze.elapsed_s(run),
        **stats,
        "cases": [
            {
                "id": row.spec_id,
                "slug": row.slug,
                "title": row.title,
                "group": row.group,
                "pack": row.pack,
                "iteration": row.iteration,
                "status": row.status,
                "error": row.error,
                "elapsed_s": row.elapsed_s,
                "steps": row.steps,
                "metrics": row.metrics,
            }
            for row in run.cases
        ],
    }
    if detail:
        data.update(analyze.detail(run, _run_dir(run.id)))
    return data


async def _recent_runs(db: AsyncSession, *, limit: int = 400) -> list[Run]:
    result = await db.execute(
        select(Run).options(selectinload(Run.cases)).order_by(Run.created_at.desc()).limit(limit)
    )
    return list(result.scalars().unique().all())


async def _load_run(db: AsyncSession, run_id: UUID) -> Run:
    result = await db.execute(select(Run).options(selectinload(Run.cases)).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(404, "run not found")
    return run


@router.post("/api/runs", status_code=201, dependencies=[Depends(require_ingest)])
async def create_run(body: RunCreate, db: AsyncSession = Depends(get_db)) -> dict:
    run = Run(
        stamp=body.stamp,
        slug=body.slug,
        mode=body.mode,
        env=body.env,
        status=body.status or "running",
        runner=body.runner,
        queries=body.queries,
        packs=body.packs,
    )
    for item in body.cases:
        run.cases.append(
            CaseRow(
                spec_id=str(item.get("id") or ""),
                slug=str(item.get("slug") or ""),
                title=str(item.get("title") or ""),
                group=str(item.get("group") or ""),
                pack=str(item.get("pack") or ""),
            )
        )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    dest = _run_dir(run.id)
    (dest / "run.json").write_text(json.dumps(body.model_dump(), ensure_ascii=False, indent=2) + "\n")
    result = await _load_run(db, run.id)
    return _dump(result)


@router.post("/api/runs/{run_id}/events", dependencies=[Depends(require_ingest)])
async def post_events(run_id: UUID, body: EventsBody, db: AsyncSession = Depends(get_db)) -> dict:
    run = await _load_run(db, run_id)
    dest = _run_dir(run.id) / "events.jsonl"
    by_id = {(row.spec_id, row.iteration): row for row in run.cases}
    with dest.open("a") as fh:
        for event in body.events:
            fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            spec_id = str(event.get("id") or "")
            iteration = int(event.get("iteration") or 0)
            row = by_id.get((spec_id, iteration))
            if row is None and spec_id:
                row = CaseRow(spec_id=spec_id, iteration=iteration, status="running")
                run.cases.append(row)
                by_id[(spec_id, iteration)] = row
            if row is None:
                continue
            kind = event.get("type")
            if kind == "start":
                row.status = "running"
            elif kind == "end":
                row.status = str(event.get("status") or row.status)
                row.error = str(event.get("error") or "")
                row.elapsed_s = float(event.get("elapsed_s") or 0)
            elif kind == "step":
                steps = list(row.steps or [])
                name = str(event.get("name") or "")
                item = {"name": name, "status": event.get("status") or "", "detail": event.get("detail") or ""}
                for i, existing in enumerate(steps):
                    if existing.get("name") == name:
                        steps[i] = item
                        break
                else:
                    steps.append(item)
                row.steps = steps
            elif kind == "metric":
                metrics = dict(row.metrics or {})
                metrics[str(event.get("key"))] = event.get("value")
                row.metrics = metrics
    await db.commit()
    return {"ok": True, "n": len(body.events)}


@router.post("/api/runs/{run_id}/finish", dependencies=[Depends(require_ingest)])
async def finish_run(run_id: UUID, body: FinishBody, db: AsyncSession = Depends(get_db)) -> dict:
    run = await _load_run(db, run_id)
    run.status = body.status
    run.summary = body.report
    run.finished_at = datetime.now(UTC)
    by_id = {(row.spec_id, row.iteration): row for row in run.cases}
    for item in body.report.get("cases") or []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("id") or ""), int(item.get("iteration") or 0))
        row = by_id.get(key)
        if row is None:
            row = CaseRow(spec_id=key[0], iteration=key[1])
            run.cases.append(row)
        row.slug = str(item.get("slug") or row.slug)
        row.title = str(item.get("title") or row.title)
        row.group = str(item.get("group") or row.group)
        row.pack = str(item.get("pack") or row.pack)
        row.status = str(item.get("status") or row.status)
        row.error = str(item.get("error") or "")
        row.elapsed_s = float(item.get("elapsed_s") or 0)
        row.steps = list(item.get("steps") or [])
        row.metrics = dict(item.get("metrics") or {})
    dest = _run_dir(run.id)
    (dest / "report.json").write_text(json.dumps(body.report, ensure_ascii=False, indent=2) + "\n")
    await db.commit()
    return _dump(await _load_run(db, run_id))


@router.post("/api/runs/{run_id}/files", dependencies=[Depends(require_ingest)])
async def upload_file(run_id: UUID, body: FileBody, db: AsyncSession = Depends(get_db)) -> dict:
    await _load_run(db, run_id)
    rel = Path(body.path)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(400, "invalid path")
    dest = _run_dir(run_id) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body.text)
    return {"ok": True, "path": rel.as_posix()}


@router.get("/api/runs")
async def list_runs(
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    env: str = "",
    status: str = "",
    hours: int | None = Query(default=None, ge=1, le=24 * 31),
    q: str = "",
) -> dict:
    stmt = select(Run).options(selectinload(Run.cases)).order_by(Run.created_at.desc()).limit(200)
    if env:
        stmt = stmt.where(Run.env == env)
    if status:
        stmt = stmt.where(Run.status == status)
    if hours:
        stmt = stmt.where(Run.created_at >= datetime.now(UTC) - timedelta(hours=hours))
    result = await db.execute(stmt)
    needle = q.strip().lower()
    runs = []
    for run in result.scalars().unique().all():
        if needle:
            hay = " ".join(
                [
                    run.slug,
                    run.stamp,
                    run.env,
                    run.mode,
                    run.runner,
                    " ".join(str(item) for item in run.packs or []),
                    " ".join(str(item) for item in run.queries or []),
                ]
            ).lower()
            if needle not in hay:
                continue
        runs.append(_dump(run))
    return {"runs": runs}


@router.get("/api/overview")
async def get_overview(
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    hours: int = Query(default=24, ge=1, le=24 * 31),
    env: str = "",
) -> dict:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    stmt = select(Run).options(selectinload(Run.cases)).where(Run.created_at >= cutoff)
    if env:
        stmt = stmt.where(Run.env == env)
    result = await db.execute(stmt.order_by(Run.created_at.asc()))
    selected = list(result.scalars().unique().all())
    catalog_ids = {row["id"] for row in analyze.catalog(await _recent_runs(db))}
    return analyze.overview(selected, hours=hours, env=env, catalog_ids=catalog_ids)


@router.get("/api/catalog")
async def get_catalog(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    rows = analyze.catalog(await _recent_runs(db))
    packs = sorted({str(item["pack"]) for item in rows if item.get("pack")})
    groups = sorted({str(item["group"]) for item in rows if item.get("group")})
    envs = sorted({str(item["env"]) for item in rows if item.get("env")})
    return {"cases": rows, "packs": packs, "groups": groups, "envs": envs}


@router.get("/api/envs")
async def get_envs(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Run.env).where(Run.env != "").distinct())
    seen = sorted({str(value) for value in result.scalars().all() if value})
    for name in ("office", "hk"):
        if name not in seen:
            seen.append(name)
    return {"envs": seen}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: UUID, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return _dump(await _load_run(db, run_id), detail=True)


@router.get("/api/runs/{run_id}/events")
async def get_events(
    run_id: UUID,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=80, ge=1, le=400),
) -> dict:
    await _load_run(db, run_id)
    path = _run_dir(run_id) / "events.jsonl"
    events: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    return {"events": events[-limit:], "total": len(events)}


@router.get("/api/runs/{run_id}/files")
async def get_files(run_id: UUID, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await _load_run(db, run_id)
    return {"files": analyze.list_files(_run_dir(run_id))}


@router.get("/api/runs/{run_id}/file")
async def get_file(
    run_id: UUID,
    path: str = Query(..., min_length=1),
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    await _load_run(db, run_id)
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts or not path:
        raise HTTPException(400, "invalid path")
    dest = (_run_dir(run_id) / rel).resolve()
    root = _run_dir(run_id).resolve()
    if dest != root and root not in dest.parents:
        raise HTTPException(400, "invalid path")
    if not dest.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(dest, filename=rel.name)


@router.get("/api/runs/{run_id}/report")
async def get_report(run_id: UUID, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Response:
    await _load_run(db, run_id)
    root = _run_dir(run_id)
    html = root / "report.html"
    if html.is_file():
        return FileResponse(html, media_type="text/html; charset=utf-8")
    report = analyze.load_report(root)
    if not report:
        raise HTTPException(404, "report not found")
    return Response(
        json.dumps(report, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
    )
