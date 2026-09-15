from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from auth import current_user
from config import ingest_token, public_url
from models import User
from skill import default_origin

router = APIRouter()

LIBRARY_SKILL = "https://lpythu.github.io/argos/skill.md"


def _origin(request: Request) -> str:
    configured = public_url()
    if configured:
        return configured
    return default_origin(str(request.base_url))


def _env_body(origin: str, token: str) -> str:
    return (
        f"# dash.env — download from this dash; do not commit\n"
        f"ARGOS_DASH_URL={origin}\n"
        f"ARGOS_TOKEN={token}\n"
    )


@router.get("/api/cli-config")
async def cli_config(request: Request, _user: User = Depends(current_user)) -> dict:
    origin = _origin(request)
    token = ingest_token()
    if not token:
        raise HTTPException(
            503,
            "ingest token is not configured (set DASH_INGEST_TOKEN on this dash)",
        )
    return {
        "url": origin,
        "token": token,
        "env": _env_body(origin, token),
        "library_skill": LIBRARY_SKILL,
        "cli_path": "/cli",
    }


@router.get("/api/cli-config/dash.env")
async def download_dash_env(request: Request, _user: User = Depends(current_user)) -> PlainTextResponse:
    origin = _origin(request)
    token = ingest_token()
    if not token:
        raise HTTPException(
            503,
            "ingest token is not configured (set DASH_INGEST_TOKEN on this dash)",
        )
    return PlainTextResponse(
        _env_body(origin, token),
        media_type="application/x-env",
        headers={"Content-Disposition": 'attachment; filename="dash.env"'},
    )
