import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from mua_platform import db
from mua_platform.main import create_app


def test_health_endpoints(client):
    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "checks": {
            "database": "ready",
            "data_directory": "ready",
            "worker": "ready",
        },
        "failed_checks": [],
    }


def test_readiness_reports_not_ready_when_database_check_fails(client, monkeypatch):
    def raise_database_error(_engine):
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr("mua_platform.main.database_is_ready", raise_database_error)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "not_ready",
            "data_directory": "ready",
            "worker": "ready",
        },
        "failed_checks": ["database"],
    }


def test_readiness_handler_uses_injected_database_check(settings):
    app = create_app(
        settings,
        readiness_database_check=lambda _engine: False,
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "not_ready",
            "data_directory": "ready",
            "worker": "ready",
        },
        "failed_checks": ["database"],
    }


def test_draining_worker_fails_readiness_but_not_liveness(client):
    client.app.state.task_worker.begin_drain()

    ready = client.get("/health/ready")
    live = client.get("/health/live")

    assert ready.status_code == 503
    assert ready.json()["checks"]["worker"] == "not_ready"
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("database_ready", "directory_ready", "worker_ready", "failed_check"),
    [
        (False, True, True, "database"),
        (True, False, True, "data_directory"),
        (True, True, False, "worker"),
    ],
)
def test_readiness_returns_503_with_failed_check(
    client,
    monkeypatch,
    database_ready,
    directory_ready,
    worker_ready,
    failed_check,
):
    monkeypatch.setattr("mua_platform.main.database_is_ready", lambda _engine: database_ready)
    monkeypatch.setattr(
        "mua_platform.main.data_directory_is_writable",
        lambda _path: directory_ready,
    )
    monkeypatch.setattr(
        type(client.app.state.task_worker),
        "is_running",
        property(lambda _worker: worker_ready),
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "ready" if database_ready else "not_ready",
            "data_directory": "ready" if directory_ready else "not_ready",
            "worker": "ready" if worker_ready else "not_ready",
        },
        "failed_checks": [failed_check],
    }


def test_readiness_returns_failed_checks_in_stable_order_without_affecting_liveness(
    client,
    monkeypatch,
):
    monkeypatch.setattr("mua_platform.main.database_is_ready", lambda _engine: False)
    monkeypatch.setattr("mua_platform.main.data_directory_is_writable", lambda _path: False)
    monkeypatch.setattr(
        type(client.app.state.task_worker),
        "is_running",
        property(lambda _worker: False),
    )

    ready = client.get("/health/ready")
    live = client.get("/health/live")

    assert ready.status_code == 503
    assert ready.json() == {
        "status": "not_ready",
        "checks": {
            "database": "not_ready",
            "data_directory": "not_ready",
            "worker": "not_ready",
        },
        "failed_checks": ["database", "data_directory", "worker"],
    }
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}


def test_data_directory_writable_probe_leaves_no_file(tmp_path):
    entries_before = set(tmp_path.iterdir())

    assert db.data_directory_is_writable(tmp_path) is True
    assert set(tmp_path.iterdir()) == entries_before


def test_data_directory_writable_probe_returns_false_for_missing_directory(tmp_path):
    assert db.data_directory_is_writable(tmp_path / "missing") is False


def test_built_spa_serves_deep_links_without_masking_api(settings, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>mua-spa</body></html>")
    (dist / "assets" / "app.js").write_text("console.log('mua')")
    monkeypatch.chdir(tmp_path)

    with TestClient(create_app(settings)) as app_client:
        deep_link = app_client.get("/tasks/task_1/report")
        asset = app_client.get("/assets/app.js")
        api_root = app_client.get("/api")
        health_root = app_client.get("/health")
        missing_api = app_client.get("/api/v1/missing")

    assert deep_link.status_code == 200
    assert "mua-spa" in deep_link.text
    assert "no-cache" in deep_link.headers["cache-control"]
    assert asset.status_code == 200
    assert api_root.status_code == 404
    assert health_root.status_code == 404
    assert missing_api.status_code == 404
    assert missing_api.json()["error"]["code"] == "not_found"
