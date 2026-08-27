from datetime import UTC, datetime, timedelta

from sqlalchemy import event, inspect, select

from cua_platform.auth.models import AuthSession, User
from cua_platform.auth.service import AuthService


def test_admin_setup_login_and_session_cookie(client):
    assert client.get("/api/v1/setup/status").json() == {"initialized": False}

    created = client.post(
        "/api/v1/setup/admin",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    assert created.status_code == 201
    assert created.json() | {"created_at": None, "updated_at": None} == {
        "id": 1,
        "username": "admin",
        "display_name": None,
        "email": None,
        "role": "admin",
        "status": "active",
        "created_at": None,
        "updated_at": None,
        "last_login_at": None,
    }
    assert "session=" in created.headers["set-cookie"]
    assert "HttpOnly" in created.headers["set-cookie"]
    assert "SameSite=lax" in created.headers["set-cookie"]
    assert "Max-Age=604800" in created.headers["set-cookie"]
    with client.app.state.session_factory() as db:
        auth_session = db.get(AuthSession, client.cookies["session"])
        lifetime = (
            auth_session.expires_at.replace(tzinfo=UTC)
            - auth_session.last_seen_at.replace(tzinfo=UTC)
        )
        assert lifetime == timedelta(days=7)
    assert client.get("/api/v1/setup/status").json() == {"initialized": True}
    assert client.get("/api/v1/auth/me").json()["username"] == "admin"

    duplicate = client.post(
        "/api/v1/setup/admin",
        json={"username": "other", "password": "StrongPassword123!"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "admin_already_initialized"

    client.headers["X-CSRF-Token"] = client.cookies["csrf"]
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["username"] == "admin"
    assert logged_in.json()["role"] == "admin"
    assert logged_in.json()["status"] == "active"
    assert client.get("/api/v1/auth/me").json()["username"] == "admin"


def test_login_rejects_wrong_password(client, initialized_admin):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_throttles_sixth_failed_attempt_without_username_disclosure(
    client,
    initialized_admin,
):
    responses = [
        client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin" if attempt % 2 else "missing-user",
                "password": "wrong-password",
            },
        )
        for attempt in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
    assert responses[5].json()["error"]["code"] == "login_rate_limited"
    assert int(responses[5].headers["Retry-After"]) > 0


def test_authenticated_write_requires_csrf(client, initialized_admin):
    client.cookies.delete("csrf")
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_invalid"


def test_auth_request_validation_enforces_credential_lengths(client):
    short_username = client.post(
        "/api/v1/setup/admin",
        json={"username": "ab", "password": "StrongPassword123!"},
    )
    assert short_username.status_code == 422
    assert short_username.json()["error"]["code"] == "request_validation_failed"

    short_password = client.post(
        "/api/v1/setup/admin",
        json={"username": "admin", "password": "too-short"},
    )
    assert short_password.status_code == 422


def test_authenticated_user_can_change_password(client, initialized_admin):
    old_session = client.cookies["session"]
    client.headers["X-CSRF-Token"] = client.cookies["csrf"]

    response = client.post(
        "/api/v1/auth/password",
        json={
            "current_password": "StrongPassword123!",
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!",
        },
    )

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.cookies.get("session") != old_session

    rejected = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    assert rejected.status_code == 401

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "NewStrongPassword123!"},
    )
    assert logged_in.status_code == 200


def test_change_password_rejects_wrong_current_password(client, initialized_admin):
    client.headers["X-CSRF-Token"] = client.cookies["csrf"]

    response = client.post(
        "/api/v1/auth/password",
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_current_password"


def test_change_password_requires_matching_confirmation(client, initialized_admin):
    client.headers["X-CSRF-Token"] = client.cookies["csrf"]

    response = client.post(
        "/api/v1/auth/password",
        json={
            "current_password": "StrongPassword123!",
            "new_password": "NewStrongPassword123!",
            "confirm_password": "DifferentPassword123!",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "password_confirmation_mismatch"


def test_database_allows_multiple_users(client):
    with client.app.state.session_factory() as db:
        db.add(User(username="first", password_hash="unused"))
        db.commit()
        db.add(User(username="second", password_hash="unused"))
        db.commit()

        users = db.scalars(select(User).order_by(User.id)).all()
        assert [user.username for user in users] == ["first", "second"]


def test_admin_can_manage_member_accounts(authenticated_client):
    created = authenticated_client.post(
        "/api/v1/users",
        json={
            "username": "alice",
            "password": "StrongPassword123!",
            "display_name": "Alice",
            "email": "alice@example.com",
            "role": "member",
        },
    )

    assert created.status_code == 201
    assert created.json()["username"] == "alice"
    assert created.json()["role"] == "member"
    assert created.json()["status"] == "active"

    listed = authenticated_client.get("/api/v1/users")
    assert listed.status_code == 200
    assert [user["username"] for user in listed.json()["items"]] == ["admin", "alice"]

    promoted = authenticated_client.patch(
        f"/api/v1/users/{created.json()['id']}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    reset = authenticated_client.post(
        f"/api/v1/users/{created.json()['id']}/reset-password",
        json={
            "new_password": "ResetPassword123!",
            "confirm_password": "ResetPassword123!",
        },
    )
    assert reset.status_code == 204

    login = authenticated_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "ResetPassword123!"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "admin"


def test_admin_can_create_users_in_batch(authenticated_client):
    created = authenticated_client.post(
        "/api/v1/users/batch",
        json={
            "users": [
                {
                    "username": "batch-member",
                    "password": "StrongPassword123!",
                    "display_name": "Batch Member",
                    "email": "batch-member@example.com",
                    "role": "member",
                },
                {
                    "username": "batch-admin",
                    "password": "StrongPassword123!",
                    "display_name": "Batch Admin",
                    "email": "batch-admin@example.com",
                    "role": "admin",
                },
            ]
        },
    )

    assert created.status_code == 201
    assert [user["username"] for user in created.json()["items"]] == [
        "batch-member",
        "batch-admin",
    ]
    assert [user["role"] for user in created.json()["items"]] == ["member", "admin"]


def test_batch_create_rejects_duplicate_usernames_without_partial_create(
    authenticated_client,
):
    response = authenticated_client.post(
        "/api/v1/users/batch",
        json={
            "users": [
                {
                    "username": "duplicate",
                    "password": "StrongPassword123!",
                    "role": "member",
                },
                {
                    "username": "duplicate",
                    "password": "StrongPassword123!",
                    "role": "admin",
                },
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "duplicate_usernames"
    listed = authenticated_client.get("/api/v1/users")
    assert "duplicate" not in [user["username"] for user in listed.json()["items"]]


def test_member_cannot_manage_users_or_runner_settings(client, authenticated_client):
    created = authenticated_client.post(
        "/api/v1/users",
        json={
            "username": "member",
            "password": "StrongPassword123!",
            "role": "member",
        },
    )
    assert created.status_code == 201

    member_client = client
    member_client.headers.clear()
    login = member_client.post(
        "/api/v1/auth/login",
        json={"username": "member", "password": "StrongPassword123!"},
    )
    assert login.status_code == 200
    member_client.headers["X-CSRF-Token"] = member_client.cookies["csrf"]

    forbidden_users = member_client.get("/api/v1/users")
    assert forbidden_users.status_code == 403
    assert forbidden_users.json()["error"]["code"] == "admin_required"

    forbidden_settings = member_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": {"product_id": "prod_1"}},
    )
    assert forbidden_settings.status_code == 403
    assert forbidden_settings.json()["error"]["code"] == "admin_required"


def test_disabled_user_cannot_login(authenticated_client):
    created = authenticated_client.post(
        "/api/v1/users",
        json={
            "username": "disabled-member",
            "password": "StrongPassword123!",
            "role": "member",
        },
    )
    assert created.status_code == 201

    disabled = authenticated_client.post(
        f"/api/v1/users/{created.json()['id']}/disable"
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    rejected = authenticated_client.post(
        "/api/v1/auth/login",
        json={"username": "disabled-member", "password": "StrongPassword123!"},
    )
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "user_disabled"


def test_unknown_user_login_still_performs_password_verification(client):
    class RecordingHasher:
        def __init__(self):
            self.calls = []

        def verify(self, password_hash: str, password: str) -> bool:
            self.calls.append((password_hash, password))
            return False

    with client.app.state.session_factory() as db:
        service = AuthService(db)
        service.hasher = RecordingHasher()

        assert service.login("missing-user", "StrongPassword123!") is None
        assert len(service.hasher.calls) == 1


def test_session_idle_expiry_is_persisted_and_enforced(client, initialized_admin):
    columns = {
        column["name"]
        for column in inspect(client.app.state.engine).get_columns("auth_sessions")
    }
    assert "last_seen_at" in columns

    session_id = client.cookies["session"]
    with client.app.state.session_factory() as db:
        auth_session = db.get(AuthSession, session_id)
        auth_session.last_seen_at = datetime.now(UTC) - timedelta(
            days=1,
            minutes=1,
        )
        auth_session.expires_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_session_remains_valid_within_twenty_four_hour_idle_window(
    client,
    initialized_admin,
):
    session_id = client.cookies["session"]
    with client.app.state.session_factory() as db:
        auth_session = db.get(AuthSession, session_id)
        auth_session.last_seen_at = datetime.now(UTC) - timedelta(hours=23)
        auth_session.expires_at = datetime.now(UTC) + timedelta(days=1)
        db.commit()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200


def test_active_session_refreshes_activity_without_extending_absolute_expiry(
    client,
    initialized_admin,
):
    columns = {
        column["name"]
        for column in inspect(client.app.state.engine).get_columns("auth_sessions")
    }
    assert "last_seen_at" in columns

    session_id = client.cookies["session"]
    old_activity = datetime.now(UTC) - timedelta(minutes=10)
    absolute_expiry = datetime.now(UTC) + timedelta(hours=1)
    with client.app.state.session_factory() as db:
        auth_session = db.get(AuthSession, session_id)
        auth_session.last_seen_at = old_activity
        auth_session.expires_at = absolute_expiry
        db.commit()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    with client.app.state.session_factory() as db:
        refreshed = db.scalar(select(AuthSession).where(AuthSession.id == session_id))
        assert refreshed.last_seen_at.replace(tzinfo=UTC) > old_activity
        assert refreshed.expires_at.replace(tzinfo=UTC) == absolute_expiry.replace(tzinfo=UTC)


def test_fresh_session_authentication_does_not_write_activity(
    client,
    initialized_admin,
):
    statements = []

    def capture_statement(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        statements.append(statement)

    event.listen(client.app.state.engine, "before_cursor_execute", capture_statement)
    try:
        response = client.get("/api/v1/auth/me")
    finally:
        event.remove(client.app.state.engine, "before_cursor_execute", capture_statement)

    assert response.status_code == 200
    assert not any(
        statement.startswith("UPDATE auth_sessions") for statement in statements
    )
