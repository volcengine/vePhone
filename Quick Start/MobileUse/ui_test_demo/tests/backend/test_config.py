from pathlib import Path

import pytest
from pydantic import ValidationError

from mua_platform.config import Settings


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
        app_env="development",
        app_secret_key="test-secret-key-at-least-32-bytes",
        app_data_dir=tmp_path,
    )

    assert settings.task_worker_drain_timeout_seconds == 30


@pytest.mark.parametrize("value", [0, 31])
def test_worker_drain_timeout_rejects_invalid_values(tmp_path, value):
    with pytest.raises(ValidationError):
        Settings(
            app_env="development",
            app_secret_key="test-secret-key-at-least-32-bytes",
            app_data_dir=tmp_path,
            task_worker_drain_timeout_seconds=value,
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
                "MOBILE_USE_ACCESS_KEY_ID=AKLTENV000000WXYZ",
                "MOBILE_USE_SECRET_ACCESS_KEY=env-secret",
                "MOBILE_USE_PRODUCT_ID=env-product",
                "MOBILE_USE_TOS_BUCKET=env-bucket",
                "MOBILE_USE_TOS_REGION=cn-beijing",
            ]
        )
    )

    settings = Settings()

    assert settings.app_secret_key == "env-secret-key-at-least-32-bytes-long"
    assert settings.app_data_dir == Path("env-data")
    assert settings.runner_setting_defaults() == {
        "runner.mobile_use.access_key_id": "AKLTENV000000WXYZ",
        "runner.mobile_use.secret_access_key": "env-secret",
        "runner.mobile_use.product_id": "env-product",
        "runner.mobile_use.tos_bucket": "env-bucket",
        "runner.mobile_use.tos_region": "cn-beijing",
    }
