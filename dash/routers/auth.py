from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth import check_password, current_user, get_user_by_login, session_cookie
from database import get_db
from models import User

router = APIRouter()


class LoginBody(BaseModel):
    login: str
    password: str


@router.post("/api/login")
async def login(body: LoginBody, response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_user_by_login(db, body.login.strip())
    if user is None or not check_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid login")
    response.set_cookie("dash_session", session_cookie(user.id), httponly=True, samesite="lax", max_age=14 * 24 * 3600)
    return {"login": user.login, "name": user.name}


@router.post("/api/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("dash_session")
    return {"ok": True}


@router.get("/api/me")
async def me(user: User = Depends(current_user)) -> dict:
    return {"login": user.login, "name": user.name}
