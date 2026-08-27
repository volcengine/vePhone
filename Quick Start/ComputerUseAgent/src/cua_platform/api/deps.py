import secrets
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from cua_platform.api.errors import api_error
from cua_platform.auth.models import AuthSession, User
from cua_platform.business.models import DEFAULT_BUSINESS_ID, BusinessSpace
from cua_platform.business.service import BusinessSpaceService

def get_db(request: Request) -> Generator[Session]:
    with request.app.state.session_factory() as db:
        yield db


Database = Annotated[Session, Depends(get_db)]


def require_session(request: Request, db: Database) -> AuthSession:
    session_id = request.cookies.get("session")
    if session_id is None:
        raise api_error(401, "authentication_required", "Authentication required")

    now = datetime.now(UTC)
    idle_timeout = timedelta(
        seconds=request.app.state.settings.auth_session_idle_timeout_seconds
    )
    activity_refresh_interval = timedelta(
        seconds=request.app.state.settings.auth_session_activity_refresh_seconds
    )
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.expires_at > now,
            AuthSession.last_seen_at > now - idle_timeout,
        )
    )
    if auth_session is None:
        raise api_error(401, "authentication_required", "Authentication required")
    last_seen_at = auth_session.last_seen_at
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    if last_seen_at <= now - activity_refresh_interval:
        auth_session.last_seen_at = now
        db.commit()
    return auth_session


CurrentSession = Annotated[AuthSession, Depends(require_session)]


def require_user(auth_session: CurrentSession, db: Database) -> User:
    user = db.get(User, auth_session.user_id)
    if user is None or user.status != "active":
        raise api_error(401, "authentication_required", "Authentication required")
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise api_error(403, "admin_required", "Administrator permission is required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_business(request: Request, db: Database) -> BusinessSpace:
    business_id = request.headers.get("X-Business-Id") or DEFAULT_BUSINESS_ID
    business = BusinessSpaceService(db).get_active(business_id)
    if business is None:
        raise api_error(404, "business_not_found", "Business space not found")
    return business


CurrentBusiness = Annotated[BusinessSpace, Depends(require_business)]


def require_csrf(request: Request, auth_session: CurrentSession) -> AuthSession:
    header_token = request.headers.get("X-CSRF-Token")
    cookie_token = request.cookies.get("csrf")
    if (
        header_token is None
        or cookie_token is None
        or not secrets.compare_digest(header_token, cookie_token)
        or not secrets.compare_digest(header_token, auth_session.csrf_token)
    ):
        raise api_error(403, "csrf_invalid", "CSRF token is invalid")
    return auth_session


CsrfSession = Annotated[AuthSession, Depends(require_csrf)]
