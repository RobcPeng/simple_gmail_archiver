from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from app.config import settings
from app.services.gmail import GmailService

router = APIRouter(prefix="/api/auth", tags=["auth"])

_gmail = GmailService(settings.client_secret_path, settings.token_path)


def get_gmail_service() -> GmailService:
    return _gmail


@router.get("/status")
async def auth_status():
    authenticated = _gmail.authenticate()
    if authenticated:
        profile = _gmail.get_profile()
        return {"authenticated": True, "email": profile.get("emailAddress")}
    has_client_secret = settings.client_secret_path.exists()
    return {"authenticated": False, "has_client_secret": has_client_secret}


@router.post("/start")
async def start_auth():
    if not settings.client_secret_path.exists():
        raise HTTPException(
            status_code=400,
            detail="client_secret.json not found. Download it from Google Cloud Console "
                   f"and place it at {settings.client_secret_path}",
        )
    redirect_uri = f"http://localhost:{settings.port}/api/auth/callback"
    auth_url = _gmail.start_oauth_flow(redirect_uri=redirect_uri)
    return {"auth_url": auth_url}


@router.get("/callback")
async def auth_callback(code: str):
    _gmail.complete_oauth_flow(code)

    # Re-initialize Gmail-dependent services now that we have a token
    from app.services.registry import registry
    registry.init_gmail_services()

    return RedirectResponse(url="/")
