import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cua_platform.auth.models import AuthSession, User
from cua_platform.auth.schemas import UserCreate, UserUpdate

DEFAULT_SESSION_LIFETIME = timedelta(days=7)
_DUMMY_PASSWORD_HASH = PasswordHasher().hash(secrets.token_urlsafe(32))


class AuthService:
    def __init__(
        self,
        db: Session,
        *,
        session_lifetime: timedelta = DEFAULT_SESSION_LIFETIME,
    ):
        self.db = db
        self.hasher = PasswordHasher()
        self.session_lifetime = session_lifetime

    def is_initialized(self) -> bool:
        return self.db.scalar(select(User.id).limit(1)) is not None

    def create_admin(self, username: str, password: str) -> tuple[User, AuthSession]:
        if self.is_initialized():
            raise ValueError("admin_already_initialized")

        user = User(
            username=username,
            password_hash=self.hasher.hash(password),
            role="admin",
            status="active",
        )
        try:
            self.db.add(user)
            self.db.flush()
            auth_session = self._new_session(user.id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("admin_already_initialized") from exc
        return user, auth_session

    def login(self, username: str, password: str) -> tuple[User, AuthSession] | None:
        user = self.db.scalar(select(User).where(User.username == username))
        try:
            verified = self.hasher.verify(
                user.password_hash if user is not None else _DUMMY_PASSWORD_HASH,
                password,
            )
        except VerifyMismatchError:
            return None
        if user is None or not verified:
            return None
        if user.status != "active":
            raise ValueError("user_disabled")

        user.last_login_at = datetime.now(UTC)
        auth_session = self._new_session(user.id)
        self.db.commit()
        return user, auth_session

    def logout(self, auth_session: AuthSession) -> None:
        self.db.delete(auth_session)
        self.db.commit()

    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        try:
            verified = self.hasher.verify(user.password_hash, current_password)
        except VerifyMismatchError:
            return False
        if not verified:
            return False
        user.password_hash = self.hasher.hash(new_password)
        self.db.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
        self.db.commit()
        return True

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.id)).all())

    def create_user(self, payload: UserCreate) -> User:
        user = User(
            username=payload.username,
            password_hash=self.hasher.hash(payload.password),
            display_name=_empty_to_none(payload.display_name),
            email=_empty_to_none(payload.email),
            role=payload.role,
            status="active",
        )
        try:
            self.db.add(user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("username_already_exists") from exc
        return user

    def create_users(self, payloads: list[UserCreate]) -> list[User]:
        usernames = [payload.username for payload in payloads]
        if len(set(usernames)) != len(usernames):
            raise ValueError("duplicate_usernames")
        existing = set(
            self.db.scalars(
                select(User.username).where(User.username.in_(usernames))
            ).all()
        )
        if existing:
            raise ValueError("username_already_exists")
        users = [
            User(
                username=payload.username,
                password_hash=self.hasher.hash(payload.password),
                display_name=_empty_to_none(payload.display_name),
                email=_empty_to_none(payload.email),
                role=payload.role,
                status="active",
            )
            for payload in payloads
        ]
        self.db.add_all(users)
        self.db.commit()
        return users

    def update_user(
        self,
        user_id: int,
        payload: UserUpdate,
        *,
        actor: User,
    ) -> User:
        user = self._get_user(user_id)
        if payload.display_name is not None:
            user.display_name = _empty_to_none(payload.display_name)
        if payload.email is not None:
            user.email = _empty_to_none(payload.email)
        if payload.role is not None and payload.role != user.role:
            if user.id == actor.id and user.role == "admin" and payload.role != "admin":
                raise ValueError("cannot_demote_self")
            user.role = payload.role
        user.updated_at = datetime.now(UTC)
        self.db.commit()
        return user

    def reset_password(
        self,
        user_id: int,
        new_password: str,
    ) -> None:
        user = self._get_user(user_id)
        user.password_hash = self.hasher.hash(new_password)
        self.db.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
        user.updated_at = datetime.now(UTC)
        self.db.commit()

    def set_user_status(
        self,
        user_id: int,
        status: str,
        *,
        actor: User,
    ) -> User:
        user = self._get_user(user_id)
        if user.id == actor.id and status == "disabled":
            raise ValueError("cannot_disable_self")
        user.status = status
        user.updated_at = datetime.now(UTC)
        if status == "disabled":
            self.db.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
        self.db.commit()
        return user

    def _get_user(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("user_not_found")
        return user

    def _new_session(self, user_id: int) -> AuthSession:
        now = datetime.now(UTC)
        auth_session = AuthSession(
            id=secrets.token_urlsafe(32),
            user_id=user_id,
            csrf_token=secrets.token_urlsafe(32),
            expires_at=now + self.session_lifetime,
            last_seen_at=now,
        )
        self.db.add(auth_session)
        return auth_session


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
