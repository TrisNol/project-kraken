from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.core.auth.models import OAuthProvider

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    providers: list[dict]


def _parse_provider(value: str) -> OAuthProvider:
    try:
        return OAuthProvider(value.lower())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown provider") from exc


def _backend_base_url(request: Request) -> str:
    configured = request.app.container.config.auth.backend_base_url()
    if configured:
        return configured.rstrip("/")

    return str(request.base_url).rstrip("/")


@router.get("/providers")
async def auth_providers(request: Request) -> AuthStatusResponse:
    oauth_service = request.app.state.oauth_service
    session_id = request.state.session_id
    statuses = oauth_service.statuses(session_id)
    return AuthStatusResponse(providers=[item.model_dump() for item in statuses])


@router.get("/{provider}/connect")
async def connect_provider(provider: str, request: Request, mode: str | None = None):
    oauth_service = request.app.state.oauth_service
    session_id = request.state.session_id
    parsed_provider = _parse_provider(provider)
    force_interactive_oauth = (mode or "").lower() == "oauth"

    # If a service token fallback is configured for this provider, no interactive OAuth
    # authorization flow is required unless explicitly requested.
    if (
        oauth_service.has_fallback_access_token(parsed_provider)
        and not force_interactive_oauth
    ):
        redirect_target = oauth_service.callback_redirect_url(
            parsed_provider,
            status="connected",
        )
        return RedirectResponse(url=redirect_target, status_code=302)

    redirect_uri = f"{_backend_base_url(request)}/auth/{parsed_provider.value}/callback"

    try:
        connect_url = await oauth_service.start_connect(
            session_id=session_id,
            provider=parsed_provider,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RedirectResponse(url=connect_url, status_code=302)


@router.get("/{provider}/callback")
async def provider_callback(
    provider: str,
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    oauth_service = request.app.state.oauth_service
    agent_manager = request.app.state.session_agent_manager
    session_id = request.state.session_id
    parsed_provider = _parse_provider(provider)

    if error:
        detail = error_description or error
        redirect_target = oauth_service.callback_redirect_with_error(
            parsed_provider,
            status="error",
            error=detail,
        )
        return RedirectResponse(url=redirect_target, status_code=302)

    if not state or not code:
        redirect_target = oauth_service.callback_redirect_with_error(
            parsed_provider,
            status="error",
            error="Missing code or state in callback.",
        )
        return RedirectResponse(url=redirect_target, status_code=302)

    try:
        await oauth_service.handle_callback(
            session_id=session_id,
            provider=parsed_provider,
            state=state,
            code=code,
        )
        agent_manager.clear_session(session_id)
        redirect_target = oauth_service.callback_redirect_url(
            parsed_provider,
            status="connected",
        )
    except Exception as exc:
        redirect_target = oauth_service.callback_redirect_with_error(
            parsed_provider,
            status="error",
            error=str(exc),
        )

    return RedirectResponse(url=redirect_target, status_code=302)


@router.post("/{provider}/disconnect")
async def disconnect_provider(provider: str, request: Request):
    oauth_service = request.app.state.oauth_service
    agent_manager = request.app.state.session_agent_manager
    session_id = request.state.session_id
    parsed_provider = _parse_provider(provider)

    oauth_service.disconnect(session_id, parsed_provider)
    agent_manager.clear_session(session_id)

    return {"status": "disconnected", "provider": parsed_provider.value}


@router.get("/me")
async def auth_me(request: Request):
    oauth_service = request.app.state.oauth_service
    session_id = request.state.session_id
    statuses = oauth_service.statuses(session_id)
    return {
        "session_id": session_id,
        "providers": [item.model_dump() for item in statuses],
    }
