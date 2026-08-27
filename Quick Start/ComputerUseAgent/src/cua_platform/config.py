import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_secret_key(data_dir: Path) -> str:
    secret_file = data_dir / "secret.key"
    if secret_file.exists():
        key = secret_file.read_text().strip()
        if len(key.encode()) >= 32:
            return key
    key = secrets.token_urlsafe(48)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(key)
    try:
        secret_file.chmod(0o600)
    except OSError:
        pass
    return key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str = ""
    app_data_dir: Path = Path("./data")
    app_base_url: str = "http://localhost:8000"
    request_max_bytes: int = Field(default=1024 * 1024, gt=0)
    auth_session_lifetime_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=300,
        le=31 * 24 * 60 * 60,
    )
    auth_session_idle_timeout_seconds: int = Field(
        default=24 * 60 * 60,
        ge=300,
        le=31 * 24 * 60 * 60,
    )
    auth_session_activity_refresh_seconds: int = Field(
        default=5 * 60,
        ge=60,
        le=60 * 60,
    )
    task_execution_timeout_seconds: int = Field(default=600, gt=0)
    cancel_confirm_timeout_seconds: int = Field(default=30, gt=0)
    task_worker_drain_timeout_seconds: int = Field(default=30, gt=0, le=30)
    device_wait_timeout_seconds: int = Field(default=300, gt=0)
    pod_pool_refresh_interval_seconds: int = Field(
        default=60,
        gt=0,
    )
    pod_pool_refresh_failure_retry_seconds: int = Field(
        default=15,
        gt=0,
    )
    task_worker_concurrency: int = Field(default=16, ge=1, le=32)
    computer_use_access_key_id: str | None = None
    computer_use_secret_access_key: str | None = None
    computer_use_account_id: str | None = None
    computer_use_tos_bucket: str | None = None
    computer_use_tos_endpoint: str | None = None
    computer_use_tos_region: str | None = None
    computer_use_max_step: str | None = None
    computer_use_timeout_seconds: str | None = None
    computer_use_callback_info: str | None = None
    computer_use_output_schema: str | None = None
    computer_use_retry_limit: str | None = None
    computer_use_system_prompt: str | None = None
    computer_use_mcp_json: str | None = None
    computer_use_max_output_tokens: str | None = None
    computer_use_request_headers: str | None = None

    @model_validator(mode="after")
    def validate_app_secret_key(self) -> "Settings":
        if not self.app_secret_key:
            self.app_secret_key = _resolve_secret_key(self.app_data_dir)
        if len(self.app_secret_key.encode()) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 UTF-8 bytes")
        if self.app_env.lower() == "production" and _is_weak_production_secret(
            self.app_secret_key
        ):
            raise ValueError("APP_SECRET_KEY is not suitable for production")
        if self.auth_session_idle_timeout_seconds > self.auth_session_lifetime_seconds:
            raise ValueError(
                "AUTH_SESSION_IDLE_TIMEOUT_SECONDS must not exceed "
                "AUTH_SESSION_LIFETIME_SECONDS"
            )
        if (
            self.auth_session_activity_refresh_seconds
            >= self.auth_session_idle_timeout_seconds
        ):
            raise ValueError(
                "AUTH_SESSION_ACTIVITY_REFRESH_SECONDS must be shorter than "
                "AUTH_SESSION_IDLE_TIMEOUT_SECONDS"
            )
        return self

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.app_data_dir / 'app.db'}"

    def runner_setting_defaults(self) -> dict[str, str]:
        defaults = {}
        for field, value in (
            ("access_key_id", self.computer_use_access_key_id),
            ("secret_access_key", self.computer_use_secret_access_key),
            ("account_id", self.computer_use_account_id),
            ("tos_bucket", self.computer_use_tos_bucket),
            ("tos_endpoint", self.computer_use_tos_endpoint),
            ("tos_region", self.computer_use_tos_region),
            ("max_step", self.computer_use_max_step),
            ("timeout_seconds", self.computer_use_timeout_seconds),
            ("callback_info", self.computer_use_callback_info),
            ("output_schema", self.computer_use_output_schema),
            ("retry_limit", self.computer_use_retry_limit),
            ("system_prompt", self.computer_use_system_prompt),
            ("mcp_json", self.computer_use_mcp_json),
            ("max_output_tokens", self.computer_use_max_output_tokens),
            ("request_headers", self.computer_use_request_headers),
        ):
            if value:
                defaults[f"runner.mobile_use.{field}"] = value
        return defaults


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _is_weak_production_secret(secret: str) -> bool:
    if secret == "test-secret-key-at-least-32-bytes" or len(set(secret)) == 1:
        return True
    return not secret.replace("change-me", "")
