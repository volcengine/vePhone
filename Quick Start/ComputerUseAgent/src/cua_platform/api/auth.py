from datetime import timedelta

from fastapi import APIRouter, Request, Response, status

from cua_platform.api.deps import AdminUser, CsrfSession, CurrentUser, Database
from cua_platform.api.errors import api_error
from cua_platform.auth.models import AuthSession
from cua_platform.auth.schemas import (
    Credentials,
    PasswordChange,
    PasswordReset,
    UserBatchCreate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from cua_platform.auth.service import AuthService

router = APIRouter(prefix="/api/v1")


def _auth_service(request: Request, db: Database) -> AuthService:
    return AuthService(
        db,
        session_lifetime=timedelta(
            seconds=request.app.state.settings.auth_session_lifetime_seconds
        ),
    )


def set_auth_cookies(
    request: Request,
    response: Response,
    auth_session: AuthSession,
) -> None:
    secure = request.app.state.settings.app_env == "production"
    max_age = request.app.state.settings.auth_session_lifetime_seconds
    response.set_cookie(
        "session",
        auth_session.id,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=max_age,
    )
    response.set_cookie(
        "csrf",
        auth_session.csrf_token,
        httponly=False,
        samesite="lax",
        secure=secure,
        max_age=max_age,
    )


@router.get("/setup/status")
def setup_status(db: Database) -> dict[str, bool]:
    return {"initialized": AuthService(db).is_initialized()}


@router.post("/setup/admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def setup_admin(
    credentials: Credentials,
    request: Request,
    response: Response,
    db: Database,
) -> UserResponse:
    try:
        user, auth_session = _auth_service(request, db).create_admin(
            credentials.username,
            credentials.password,
        )
    except ValueError as exc:
        if str(exc) == "admin_already_initialized":
            raise api_error(
                409,
                "admin_already_initialized",
                "Administrator has already been initialized",
            ) from exc
        raise

    set_auth_cookies(request, response, auth_session)
    return UserResponse.model_validate(user)


@router.post("/auth/login", response_model=UserResponse)
def login(
    credentials: Credentials,
    request: Request,
    response: Response,
    db: Database,
) -> UserResponse:
    client_key = request.client.host if request.client is not None else "unknown"
    retry_after = request.app.state.login_throttle.begin(
        client_key,
        request.app.state.auth_clock.now(),
    )
    if retry_after is not None:
        raise api_error(
            429,
            "login_rate_limited",
            "Too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        result = _auth_service(request, db).login(
            credentials.username,
            credentials.password,
        )
    except ValueError as exc:
        if str(exc) == "user_disabled":
            raise api_error(403, "user_disabled", "User is disabled") from exc
        raise
    if result is None:
        raise api_error(401, "invalid_credentials", "Invalid username or password")

    request.app.state.login_throttle.clear(client_key)
    user, auth_session = result
    set_auth_cookies(request, response, auth_session)
    return UserResponse.model_validate(user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth_session: CsrfSession, db: Database) -> Response:
    AuthService(db).logout(auth_session)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("session")
    response.delete_cookie("csrf")
    return response


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChange,
    user: CurrentUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> Response:
    if payload.new_password != payload.confirm_password:
        raise api_error(
            422,
            "password_confirmation_mismatch",
            "Password confirmation does not match",
        )
    changed = AuthService(db).change_password(
        user,
        payload.current_password,
        payload.new_password,
    )
    if not changed:
        raise api_error(
            400,
            "invalid_current_password",
            "Current password is invalid",
        )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("session")
    response.delete_cookie("csrf")
    return response


@router.get("/auth/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.get("/users", response_model=UserListResponse)
def list_users(
    _admin: AdminUser,
    db: Database,
) -> UserListResponse:
    return UserListResponse(
        items=[
            UserResponse.model_validate(user)
            for user in AuthService(db).list_users()
        ]
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _admin: AdminUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> UserResponse:
    try:
        user = AuthService(db).create_user(payload)
    except ValueError as exc:
        if str(exc) == "username_already_exists":
            raise api_error(
                409,
                "username_already_exists",
                "Username already exists",
            ) from exc
        raise
    return UserResponse.model_validate(user)


@router.post("/users/batch", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
def create_users(
    payload: UserBatchCreate,
    _admin: AdminUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> UserListResponse:
    try:
        users = AuthService(db).create_users(payload.users)
    except ValueError as exc:
        code = str(exc)
        if code == "duplicate_usernames":
            raise api_error(422, code, "Duplicate usernames in request") from exc
        if code == "username_already_exists":
            raise api_error(409, code, "Username already exists") from exc
        raise
    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users]
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: AdminUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> UserResponse:
    try:
        user = AuthService(db).update_user(user_id, payload, actor=admin)
    except ValueError as exc:
        code = str(exc)
        if code == "user_not_found":
            raise api_error(404, code, "User not found") from exc
        if code == "cannot_demote_self":
            raise api_error(400, code, "Administrator cannot demote self") from exc
        raise
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: int,
    payload: PasswordReset,
    _admin: AdminUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> Response:
    if payload.new_password != payload.confirm_password:
        raise api_error(
            422,
            "password_confirmation_mismatch",
            "Password confirmation does not match",
        )
    try:
        AuthService(db).reset_password(user_id, payload.new_password)
    except ValueError as exc:
        if str(exc) == "user_not_found":
            raise api_error(404, "user_not_found", "User not found") from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/disable", response_model=UserResponse)
def disable_user(
    user_id: int,
    admin: AdminUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> UserResponse:
    try:
        user = AuthService(db).set_user_status(user_id, "disabled", actor=admin)
    except ValueError as exc:
        code = str(exc)
        if code == "user_not_found":
            raise api_error(404, code, "User not found") from exc
        if code == "cannot_disable_self":
            raise api_error(400, code, "Administrator cannot disable self") from exc
        raise
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/enable", response_model=UserResponse)
def enable_user(
    user_id: int,
    admin: AdminUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> UserResponse:
    try:
        user = AuthService(db).set_user_status(user_id, "active", actor=admin)
    except ValueError as exc:
        if str(exc) == "user_not_found":
            raise api_error(404, "user_not_found", "User not found") from exc
        raise
    return UserResponse.model_validate(user)
