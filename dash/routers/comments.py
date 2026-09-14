from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import current_user
from database import get_db
from models import Comment, Run, User

router = APIRouter()


class CommentBody(BaseModel):
    body: str
    case_id: str = ""


def _dump(row: Comment) -> dict:
    return {
        "id": str(row.id),
        "case_id": row.case_id,
        "body": row.body,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "author": {"login": row.author.login, "name": row.author.name},
    }


@router.get("/api/runs/{run_id}/comments")
async def list_comments(run_id: UUID, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    if await db.get(Run, run_id) is None:
        raise HTTPException(404, "run not found")
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.run_id == run_id)
        .order_by(Comment.created_at.asc())
    )
    return {"comments": [_dump(row) for row in result.scalars().all()]}


@router.post("/api/runs/{run_id}/comments", status_code=201)
async def add_comment(
    run_id: UUID,
    body: CommentBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if await db.get(Run, run_id) is None:
        raise HTTPException(404, "run not found")
    text = body.body.strip()
    if not text:
        raise HTTPException(400, "empty comment")
    row = Comment(run_id=run_id, author_id=user.id, case_id=body.case_id.strip(), body=text)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    loaded = await db.execute(select(Comment).options(selectinload(Comment.author)).where(Comment.id == row.id))
    return _dump(loaded.scalar_one())
