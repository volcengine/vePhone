from pathlib import Path

import pytest
from pydantic import ValidationError

from cua_platform.config import Settings


@pytest.mark.parametrize(
    "secret",
    [
        "test-secret-key-at-least-32-bytes",
        "change-mechange-mechange-mechange-me",
        "x" * 32,
    ],
)
def test_production_rejects_weak_secret_before_database_creation(tmp_path, secret):
    with pytest.raises(
        ValidationError,
        match="APP_SECRET_KEY is not suitable for production",
    ):
        Settings(
            app_env="production",
            app_secret_key=secret,
            app_data_dir=tmp_path,
        )


def test_secret_requires_at_least_32_utf8_bytes(tmp_path):
    with pytest.raises(ValidationError, match="APP_SECRET_KEY"):
        Settings(
            app_env="development",
            app_secret_key="密" * 10,
            app_data_dir=tmp_path,
        )


def test_secret_accepts_32_utf8_bytes(tmp_path):
    settings = Settings(
        app_env="development",
        app_secret_key="密" * 10 + "ab",
        app_data_dir=tmp_path,
    )

    assert len(settings.app_secret_key.encode()) == 32


def test_worker_drain_timeout_defaults_to_30_seconds(tmp_path):
    settings = Settings(
        app_secret_key="test-secret-key-at-least-32-bytes",
        app_data_dir=tmp_path,
    )

    assert settings.task_worker_drain_timeout_seconds == 30


def test_worker_drain_timeout_must_be_positive(tmp_path):
    with pytest.raises(ValidationError):
        Settings(
            app_secret_key="test-secret-key-at-least-32-bytes",
            app_data_dir=tmp_path,
            task_worker_drain_timeout_seconds=0,
        )


@pytest.mark.parametrize("timeout_seconds", [31, 60])
def test_worker_drain_timeout_must_not_exceed_30_seconds(
    tmp_path,
    timeout_seconds,
):
    with pytest.raises(ValidationError):
        Settings(
            app_secret_key="test-secret-key-at-least-32-bytes",
            app_data_dir=tmp_path,
            task_worker_drain_timeout_seconds=timeout_seconds,
        )


def test_settings_loads_repository_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "APP_SECRET_KEY=env-secret-key-at-least-32-bytes-long",
                "APP_DATA_DIR=./env-data",
                "COMPUTER_USE_ACCESS_KEY_ID=AKLTENV000000WXYZ",
                "COMPUTER_USE_SECRET_ACCESS_KEY=env-secret",
                "COMPUTER_USE_ACCOUNT_ID=2103274899",
                "COMPUTER_USE_TOS_BUCKET=env-bucket",
                "COMPUTER_USE_TOS_REGION=cn-beijing",
            ]
        )
    )

    settings = Settings()

    assert settings.app_secret_key == "env-secret-key-at-least-32-bytes-long"
    assert settings.app_data_dir == Path("env-data")
    assert settings.runner_setting_defaults() == {
        "runner.mobile_use.access_key_id": "AKLTENV000000WXYZ",
        "runner.mobile_use.secret_access_key": "env-secret",
        "runner.mobile_use.account_id": "2103274899",
        "runner.mobile_use.tos_bucket": "env-bucket",
        "runner.mobile_use.tos_region": "cn-beijing",
    }
