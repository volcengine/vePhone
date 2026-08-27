import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from cua_platform.pods.schemas import ListPodPage
from cua_platform.runners.universal_gateway import UniversalRemoteError
from cua_platform.settings.repository import SettingRepository


COMPUTER_USE_CONFIG = {
    "access_key_id": "AKLT00000000WXYZ",
    "secret_access_key": "secret-value",
    "account_id": "2103274899",
    "product_id": "prod_123",
    "pod_id": "pod_123",
    "ark_api_key": "ark-value",
    "tos_bucket": "bucket-name",
    "tos_region": "cn-beijing",
    "request_headers": {"X-Env": "test", "X-Secret": "header-secret"},
}


def test_runner_settings_default_to_mobile_use_and_hide_unconfigured_values(authenticated_client):
    response = authenticated_client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "mobile_use",
        "mobile_use": {
            "access_key_id": {"configured": False},
            "secret_access_key": {"configured": False},
            "product_id": None,
            "account_id": None,
            "sts_role_trn": None,
            "stream_token_ttl_seconds": 600,
            "pod_id": None,
            "ark_api_key": {"configured": False},
            "tos_bucket": None,
            "tos_endpoint": None,
            "tos_region": None,
            "use_base64_screenshot": False,
            "max_step": 100,
            "timeout_seconds": 120,
            "callback_info": None,
            "output_schema": None,
            "retry_limit": 3,
            "system_prompt": None,
            "screen_record": False,
            "mcp_json": None,
            "max_output_tokens": None,
            "gps_info": None,
            "request_headers": {"configured": False, "names": []},
        },
    }


def test_runner_settings_are_replace_only_and_masked(authenticated_client):
    saved = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_CONFIG},
    )

    assert saved.status_code == 200
    body = saved.json()
    serialized = saved.text
    assert body["mode"] == "mobile_use"
    assert body["mobile_use"]["access_key_id"] == {
        "configured": True,
        "hint": "AKLT****WXYZ",
    }
    assert body["mobile_use"]["secret_access_key"] == {"configured": True}
    assert body["mobile_use"]["ark_api_key"] == {"configured": True}
    assert body["mobile_use"]["request_headers"] == {
        "configured": True,
        "names": ["X-Env", "X-Secret"],
    }
    assert "secret-value" not in serialized
    assert "ark-value" not in serialized
    assert "header-secret" not in serialized

    retained = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": {"pod_id": "pod_456"}},
    )

    assert retained.status_code == 200
    assert retained.json()["mobile_use"]["pod_id"] == "pod_456"
    reread = authenticated_client.get("/api/v1/settings")
    assert reread.json()["mobile_use"]["access_key_id"]["hint"] == "AKLT****WXYZ"
    assert reread.json()["mobile_use"]["product_id"] == "prod_123"
    assert reread.json()["mobile_use"]["request_headers"] == {
        "configured": True,
        "names": ["X-Env", "X-Secret"],
    }


def test_runner_settings_clear_optional_fields_with_null(authenticated_client):
    saved = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                **COMPUTER_USE_CONFIG,
                "callback_info": {"url": "https://callback.example.com"},
                "output_schema": '{"type":"object"}',
                "system_prompt": "custom system prompt",
                "mcp_json": '{"mcpServers":{}}',
                "max_output_tokens": 2048,
                "request_headers": {"X-Env": "test"},
            },
        },
    )
    assert saved.status_code == 200, saved.text

    cleared = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "callback_info": None,
                "output_schema": None,
                "system_prompt": None,
                "mcp_json": None,
                "max_output_tokens": None,
                "request_headers": None,
            },
        },
    )

    assert cleared.status_code == 200, cleared.text
    mobile_use = cleared.json()["mobile_use"]
    assert mobile_use["callback_info"] is None
    assert mobile_use["output_schema"] is None
    assert mobile_use["system_prompt"] is None
    assert mobile_use["mcp_json"] is None
    assert mobile_use["max_output_tokens"] is None
    assert mobile_use["request_headers"] == {"configured": False, "names": []}
    with authenticated_client.app.state.session_factory() as db:
        values = SettingRepository(
            db,
            authenticated_client.app.state.setting_cipher,
            authenticated_client.app.state.settings.runner_setting_defaults(),
        ).list_decrypted()
    assert "None" not in values.values()
    for field in (
        "callback_info",
        "output_schema",
        "system_prompt",
        "mcp_json",
        "max_output_tokens",
        "request_headers",
    ):
        assert f"runner.mobile_use.{field}" not in values


def test_runner_settings_are_scoped_by_business(authenticated_client):
    created = authenticated_client.post(
        "/api/v1/business-spaces",
        json={"name": "搜索业务"},
    )
    assert created.status_code == 201
    search_business_id = created.json()["id"]

    default_saved = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                **COMPUTER_USE_CONFIG,
                "product_id": "product-default",
                "request_headers": {"X-Biz": "default"},
            },
        },
    )
    assert default_saved.status_code == 200

    authenticated_client.headers["X-Business-Id"] = search_business_id
    try:
        search_saved = authenticated_client.put(
            "/api/v1/settings/runner",
            json={
                "mode": "mobile_use",
                "mobile_use": {
                    **COMPUTER_USE_CONFIG,
                    "product_id": "product-search",
                    "request_headers": {"X-Biz": "search"},
                },
            },
        )
        assert search_saved.status_code == 200
        assert search_saved.json()["mobile_use"]["product_id"] == "product-search"

        search_read = authenticated_client.get("/api/v1/settings")
        assert search_read.status_code == 200
        assert search_read.json()["mobile_use"]["product_id"] == "product-search"
        assert search_read.json()["mobile_use"]["request_headers"] == {
            "configured": True,
            "names": ["X-Biz"],
        }
    finally:
        authenticated_client.headers.pop("X-Business-Id", None)

    default_read = authenticated_client.get("/api/v1/settings")
    assert default_read.status_code == 200
    assert default_read.json()["mobile_use"]["product_id"] == "product-default"
    assert default_read.json()["mobile_use"]["request_headers"] == {
        "configured": True,
        "names": ["X-Biz"],
    }


def test_runner_settings_reject_duplicate_product_id_across_businesses(
    authenticated_client,
):
    created = authenticated_client.post(
        "/api/v1/business-spaces",
        json={"name": "重复 Product 业务"},
    )
    assert created.status_code == 201
    duplicate_business_id = created.json()["id"]

    first = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                **COMPUTER_USE_CONFIG,
                "product_id": "product-unique",
            },
        },
    )
    assert first.status_code == 200

    authenticated_client.headers["X-Business-Id"] = duplicate_business_id
    try:
        duplicate = authenticated_client.put(
            "/api/v1/settings/runner",
            json={
                "mode": "mobile_use",
                "mobile_use": {
                    **COMPUTER_USE_CONFIG,
                    "product_id": "product-unique",
                },
            },
        )
    finally:
        authenticated_client.headers.pop("X-Business-Id", None)

    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "runner_product_id_conflict"
    assert duplicate.json()["error"]["details"] == {"field": "product_id"}


def test_runner_settings_reject_reserved_request_headers(authenticated_client):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                **COMPUTER_USE_CONFIG,
                "request_headers": {"Authorization": "Bearer blocked"},
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_setting_value_invalid"
    assert response.json()["error"]["details"] == {"field": "request_headers"}


def test_short_access_key_is_configured_without_exposing_a_partial_hint(
    authenticated_client,
):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                **COMPUTER_USE_CONFIG,
                "access_key_id": "short",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["mobile_use"]["access_key_id"] == {
        "configured": True,
        "hint": "configured",
    }


def test_switching_to_mock_retains_mobile_use_secrets(authenticated_client):
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_CONFIG},
    )
    assert configured.status_code == 200

    switched = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mock"},
    )

    assert switched.status_code == 200
    assert switched.json()["mode"] == "mock"
    assert switched.json()["mobile_use"]["secret_access_key"] == {"configured": True}
    assert switched.json()["mobile_use"]["ark_api_key"] == {"configured": True}


def test_settings_endpoints_require_authentication(client):
    read = client.get("/api/v1/settings")
    updated = client.put("/api/v1/settings/runner", json={"mode": "mock"})

    assert read.status_code == 401
    assert updated.status_code == 401


def test_runner_settings_update_requires_csrf(authenticated_client):
    csrf = authenticated_client.headers.pop("X-CSRF-Token")
    try:
        response = authenticated_client.put(
            "/api/v1/settings/runner",
            json={"mode": "mock"},
        )
    finally:
        authenticated_client.headers["X-CSRF-Token"] = csrf

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_invalid"


@pytest.mark.parametrize("invalid_value", [None, "", "   "])
def test_runner_settings_reject_explicit_empty_values(
    authenticated_client,
    invalid_value,
):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mock",
            "mobile_use": {"pod_id": invalid_value},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_setting_value_invalid"
    assert response.json()["error"]["details"] == {"field": "pod_id"}


def test_first_mobile_use_switch_lists_required_fields_in_fixed_order(authenticated_client):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_settings_incomplete"
    assert response.json()["error"]["details"] == {
        "missing_fields": [
            "access_key_id",
            "secret_access_key",
                "account_id",
        ]
    }


def test_first_mobile_use_switch_does_not_require_legacy_pod_id(authenticated_client):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "secret-value",
                    "account_id": "2103274899",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["mobile_use"]["pod_id"] is None


def test_successful_update_writes_sanitized_audit_event(
    authenticated_client,
    initialized_admin,
):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "pod_id": "pod_123",
                    "account_id": "2103274899",
                "secret_access_key": "secret-value",
                "access_key_id": "AKLT00000000WXYZ",
            },
        },
    )
    assert response.status_code == 200

    with authenticated_client.app.state.session_factory() as db:
        row = db.execute(
            text(
                "SELECT action, actor_user_id, details_json "
                "FROM audit_events ORDER BY created_at"
            )
        ).one()

    assert row.action == "runner_settings_updated"
    assert row.actor_user_id == initialized_admin["id"]
    assert json.loads(row.details_json) == {
        "mode": "mobile_use",
        "changed_fields": [
            "access_key_id",
                "account_id",
            "pod_id",
            "secret_access_key",
        ],
    }
    assert "AKLT00000000WXYZ" not in row.details_json
    assert "secret-value" not in row.details_json
    assert "prod_123" not in row.details_json
    assert "pod_123" not in row.details_json


def test_failed_update_does_not_write_settings_or_audit(authenticated_client):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {"access_key_id": "AKLT00000000WXYZ"},
        },
    )

    assert response.status_code == 422
    with authenticated_client.app.state.session_factory() as db:
        setting_count = db.execute(text("SELECT COUNT(*) FROM settings")).scalar_one()
        audit_count = db.execute(text("SELECT COUNT(*) FROM audit_events")).scalar_one()
    assert setting_count == 0
    assert audit_count == 0


def test_failed_pod_discovery_rolls_back_settings_and_audit(authenticated_client):
    class FailingPodGateway:
        async def list_all(self, _config):
            raise UniversalRemoteError(
                "remote_unavailable",
                "req-settings-failure",
                retryable=True,
                response_received=False,
            )

    authenticated_client.app.state.pod_gateway = FailingPodGateway()
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_CONFIG},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "pod_pool_discovery_failed"
    assert authenticated_client.get("/api/v1/settings").json()["mode"] == "mobile_use"
    with authenticated_client.app.state.session_factory() as db:
        setting_count = db.execute(text("SELECT COUNT(*) FROM settings")).scalar_one()
        audit_count = db.execute(text("SELECT COUNT(*) FROM audit_events")).scalar_one()
    assert setting_count == 0
    assert audit_count == 0


def test_remote_settings_discovery_does_not_hold_sqlite_write_lock(
    authenticated_client,
):
    class BlockingPodGateway:
        def __init__(self):
            self.started = Event()
            self.release = Event()

        async def list_all(self, _config):
            self.started.set()
            await asyncio.to_thread(self.release.wait)
            return ListPodPage(items=(), next_token=None, request_id="req-lock")

    gateway = BlockingPodGateway()
    app = authenticated_client.app
    app.state.pod_gateway = gateway
    cookies = dict(authenticated_client.cookies)
    csrf_token = authenticated_client.cookies["csrf"]
    with app.state.engine.begin() as connection:
        connection.execute(text("CREATE TABLE settings_lock_probe (value TEXT)"))

    def update_settings():
        with TestClient(app, raise_server_exceptions=False) as concurrent_client:
            concurrent_client.cookies.update(cookies)
            concurrent_client.headers["X-CSRF-Token"] = csrf_token
            return concurrent_client.put(
                "/api/v1/settings/runner",
                json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_CONFIG},
            )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(update_settings)
        assert gateway.started.wait(timeout=1)
        try:
            with sqlite3.connect(app.state.settings.database_url.removeprefix("sqlite:///")) as db:
                db.execute("PRAGMA busy_timeout=50")
                db.execute("INSERT INTO settings_lock_probe(value) VALUES ('concurrent')")
                db.commit()
        finally:
            gateway.release.set()
        response = future.result(timeout=2)

    assert response.status_code == 200


def test_concurrent_runner_settings_updates_are_serialized(authenticated_client):
    class SequencedPodGateway:
        def __init__(self):
            self.first_started = Event()
            self.second_started = Event()
            self.release_first = Event()

        async def list_all(self, config):
            if config.product_id == "product-a":
                self.first_started.set()
                await asyncio.to_thread(self.release_first.wait)
            elif config.product_id == "product-b":
                self.second_started.set()
            return ListPodPage(
                items=(),
                next_token=None,
                request_id=f"req-{config.product_id}",
            )

    gateway = SequencedPodGateway()
    authenticated_client.app.state.pod_gateway = gateway

    def update(product_id: str):
        return authenticated_client.put(
            "/api/v1/settings/runner",
            json={
                "mode": "mobile_use",
                "mobile_use": {
                    **COMPUTER_USE_CONFIG,
                    "product_id": product_id,
                },
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(update, "product-a")
        assert gateway.first_started.wait(timeout=1)
        second = executor.submit(update, "product-b")
        try:
            assert not gateway.second_started.wait(timeout=0.1)
        finally:
            gateway.release_first.set()
        assert first.result(timeout=2).status_code == 200
        assert second.result(timeout=2).status_code == 200
    assert gateway.second_started.is_set()
