import colorsys
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cua_platform.cases.models import TestCase as CaseModel
from cua_platform.db import (
    Base,
    _TAG_COLOR_CANDIDATES,
    _unused_tag_color,
    ensure_schema_migrations,
)
from cua_platform.pods.repository import PodRepository
from cua_platform.test_plans.models import TagColorRegistry


def _relative_luminance(color: str | tuple[float, float, float]) -> float:
    channels = (
        tuple(int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
        if isinstance(color, str)
        else color
    )
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(
    first: str | tuple[float, float, float],
    second: str | tuple[float, float, float],
) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def _composite_over_white(
    color: str,
    alpha: int = 0x1A,
) -> tuple[float, float, float]:
    opacity = alpha / 255
    return tuple(
        (int(color[index : index + 2], 16) / 255) * opacity
        + 1 * (1 - opacity)
        for index in (1, 3, 5)
    )


def _insert_test_plan(
    connection,
    *,
    plan_id: str,
    name: str,
    name_key: str,
    test_type: str = "regression",
    deleted_at: datetime | None = None,
) -> None:
    now = datetime(2026, 7, 30, 0, 0, tzinfo=UTC)
    connection.execute(
        text(
            """
            INSERT INTO test_plans (
                id, name, name_key, description, test_type, tags, created_by,
                created_at, updated_at, deleted_at
            )
            VALUES (
                :id, :name, :name_key, NULL, :test_type, '[]', 'admin',
                :now, :now, :deleted_at
            )
            """
        ),
        {
            "id": plan_id,
            "name": name,
            "name_key": name_key,
            "test_type": test_type,
            "now": now,
            "deleted_at": deleted_at,
        },
    )


def _insert_test_case(connection, case_id: str) -> None:
    now = datetime(2026, 7, 30, 0, 0, tzinfo=UTC)
    connection.execute(
        text(
            """
            INSERT INTO test_cases (
                id, title, module, content_markdown, tags, automation_level,
                execution_count, pass_count, fail_count, last_executed_at,
                created_by, created_at, updated_at
            )
            VALUES (
                :id, :id, NULL, '- test', '[]', 'manual_confirm',
                0, 0, 0, NULL, 'admin', :now, :now
            )
            """
        ),
        {"id": case_id, "now": now},
    )


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def test_business_space_concurrency_limit_is_added_to_legacy_schema():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE business_spaces (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        name_key VARCHAR(100) NOT NULL,
                        description TEXT,
                        is_default BOOLEAN NOT NULL,
                        created_by VARCHAR(100) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        archived_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO business_spaces (
                        id, name, name_key, description, is_default,
                        created_by, created_at, updated_at, archived_at
                    )
                    VALUES (
                        'biz_default', '默认业务', '默认业务', NULL, 1,
                        'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL
                    )
                    """
                )
            )

        ensure_schema_migrations(engine)

        columns = {
            column["name"] for column in inspect(engine).get_columns("business_spaces")
        }
        assert "task_concurrency_limit" in columns
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT task_concurrency_limit FROM business_spaces "
                    "WHERE id = 'biz_default'"
                )
            ).scalar_one() == 4
    finally:
        engine.dispose()


def _create_migrated_foreign_key_engine():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE test_cases (
                    id VARCHAR(40) NOT NULL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    tags JSON DEFAULT '[]'
                )
                """
            )
        )
    ensure_schema_migrations(engine)
    return engine


def _insert_task_batch(connection, batch_id: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO task_batches (
                id, name, test_type, selection_mode, selection_snapshot,
                device_strategy, pod_ids, concurrency,
                device_wait_timeout_seconds, runner_type, config_snapshot,
                execution_status, idempotency_key, request_fingerprint,
                created_by, created_at
            )
            VALUES (
                :id, :id, 'case', 'manual', '{}', 'auto', '[]', 1, 300,
                'mobile_use', '{}', 'queued', :idempotency_key, '{}',
                'admin', :created_at
            )
            """
        ),
        {
            "id": batch_id,
            "idempotency_key": f"idempotency-{batch_id}",
            "created_at": datetime(2026, 7, 30, 0, 0, tzinfo=UTC),
        },
    )


def _insert_plan_execution(
    connection,
    *,
    execution_id: str,
    plan_id: str,
    batch_id: str,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO plan_executions (
                id, test_plan_id, task_batch_id, plan_name_snapshot,
                plan_tags_snapshot, case_ids_snapshot,
                device_strategy_snapshot, pod_ids_snapshot,
                concurrency_snapshot, runner_type_snapshot, config_snapshot,
                created_by, created_at
            )
            VALUES (
                :id, :plan_id, :batch_id, '计划快照', '[]', '[]',
                'auto', '[]', 1, 'mobile_use', '{}', 'admin', :created_at
            )
            """
        ),
        {
            "id": execution_id,
            "plan_id": plan_id,
            "batch_id": batch_id,
            "created_at": datetime(2026, 7, 30, 0, 0, tzinfo=UTC),
        },
    )


def test_task_start_state_migration_preserves_unknown_dispatch_boundary():
    engine = create_engine("sqlite://")
    now = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE test_cases (id VARCHAR(40) PRIMARY KEY)"))
            connection.execute(text("INSERT INTO test_cases (id) VALUES ('case_start_state')"))
            connection.execute(
                text(
                    """
                    CREATE TABLE tasks (
                        id VARCHAR(40) PRIMARY KEY,
                        case_id VARCHAR(40) NOT NULL,
                        script_version_id VARCHAR(40),
                        runner_type VARCHAR(32) NOT NULL,
                        scenario VARCHAR(32) NOT NULL,
                        execution_status VARCHAR(15) NOT NULL,
                        verdict VARCHAR(12),
                        failure_type VARCHAR(64),
                        idempotency_key VARCHAR(255) NOT NULL,
                        request_fingerprint VARCHAR NOT NULL,
                        remote_run_id VARCHAR,
                        version INTEGER NOT NULL,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO tasks (
                        id, case_id, runner_type, scenario, execution_status,
                        idempotency_key, request_fingerprint, remote_run_id,
                        version, created_at
                    ) VALUES
                        ('queued', 'case_start_state', 'mock', 'queued', 'queued',
                         'q', '{}', NULL, 1, :now),
                        ('unknown', 'case_start_state', 'mock', 'unknown', 'running',
                         'u', '{}', NULL, 1, :now),
                        ('attached', 'case_start_state', 'mock', 'attached', 'running',
                         'a', '{}', 'run-1', 1, :now)
                    """
                ),
                {"now": now},
            )

        Base.metadata.create_all(engine)
        ensure_schema_migrations(engine)

        columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
        assert {"start_state", "start_attempted_at"} <= columns
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, start_state FROM tasks ORDER BY id")
            ).all()
        assert rows == [
            ("attached", "attached"),
            ("queued", "pending"),
            ("unknown", "dispatching"),
        ]
    finally:
        engine.dispose()


def test_discovered_pods_legacy_schema_is_migrated_for_current_model():
    engine = create_engine("sqlite://")
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE discovered_pods (
                        id VARCHAR(40) NOT NULL,
                        product_id VARCHAR(255) NOT NULL,
                        pod_id VARCHAR(255) NOT NULL,
                        pod_name VARCHAR(255) NOT NULL,
                        remote_status VARCHAR(32) NOT NULL,
                        online BOOLEAN NOT NULL,
                        discovery_state VARCHAR(16) NOT NULL,
                        last_seen_at DATETIME NOT NULL,
                        last_checked_at DATETIME,
                        last_request_id VARCHAR(128),
                        last_assigned_at DATETIME,
                        consecutive_failures INTEGER NOT NULL,
                        cooldown_until DATETIME,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (id),
                        CONSTRAINT unique_discovered_product_pod UNIQUE (product_id, pod_id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO discovered_pods (
                        id, product_id, pod_id, pod_name, remote_status, online,
                        discovery_state, last_seen_at, consecutive_failures,
                        created_at, updated_at
                    )
                    VALUES (
                        'pod_legacy', 'product_legacy', 'pod_legacy',
                        'Legacy Pod', 'running', 1, 'active', :now, 0, :now, :now
                    )
                    """
                ),
                {"now": now},
            )

        ensure_schema_migrations(engine)

        columns = {column["name"] for column in inspect(engine).get_columns("discovered_pods")}
        assert "pod_status_code" in columns
        assert "stream_status" in columns

        with Session(engine) as db:
            row = PodRepository(db).get("product_legacy", "pod_legacy")

        assert row is not None
        assert row.pod_status_code == 1
        assert row.stream_status is None
    finally:
        engine.dispose()


def test_test_cases_legacy_required_columns_are_dropped_for_current_model():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        mode VARCHAR(32) NOT NULL,
                        app_name VARCHAR(200) NOT NULL,
                        app_version VARCHAR(100) NOT NULL,
                        preconditions JSON NOT NULL,
                        steps JSON NOT NULL,
                        assertions JSON NOT NULL,
                        automation_level VARCHAR(32) NOT NULL,
                        mock_scenario VARCHAR(32) NOT NULL,
                        module VARCHAR(100),
                        content_markdown TEXT,
                        tags JSON DEFAULT '[]',
                        execution_count INTEGER DEFAULT 0,
                        pass_count INTEGER DEFAULT 0,
                        fail_count INTEGER DEFAULT 0,
                        last_executed_at DATETIME,
                        created_by VARCHAR(100) DEFAULT 'system',
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )

        ensure_schema_migrations(engine)

        columns = {column["name"] for column in inspect(engine).get_columns("test_cases")}
        assert "mode" not in columns
        assert "app_name" not in columns
        assert "app_version" not in columns
        assert "preconditions" not in columns
        assert "steps" not in columns
        assert "assertions" not in columns
        assert "mock_scenario" not in columns

        with Session(engine) as db:
            db.add(
                CaseModel(
                    id="case_current",
                    title="当前用例",
                    module=None,
                    content_markdown="## 执行任务\n- 打开应用",
                    tags=["smoke"],
                    automation_level="auto",
                    created_by="admin",
                )
            )
            db.commit()

        with engine.connect() as connection:
            title = connection.execute(
                text("SELECT title FROM test_cases WHERE id = 'case_current'")
            ).scalar_one()
        assert title == "当前用例"
    finally:
        engine.dispose()


def test_tasks_legacy_script_requirement_is_removed_without_losing_relations():
    engine = create_engine("sqlite://")
    now = datetime(2026, 7, 29, 0, 0, tzinfo=UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        module VARCHAR(100),
                        content_markdown TEXT,
                        tags JSON DEFAULT '[]',
                        automation_level VARCHAR(32) NOT NULL,
                        execution_count INTEGER DEFAULT 0,
                        pass_count INTEGER DEFAULT 0,
                        fail_count INTEGER DEFAULT 0,
                        last_executed_at DATETIME,
                        created_by VARCHAR(100) DEFAULT 'system',
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE script_versions "
                    "(id VARCHAR(40) NOT NULL PRIMARY KEY)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE tasks (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        case_id VARCHAR(40) NOT NULL,
                        script_version_id VARCHAR(40) NOT NULL,
                        runner_type VARCHAR(32) NOT NULL,
                        scenario VARCHAR(32) NOT NULL,
                        execution_status VARCHAR(15) NOT NULL,
                        verdict VARCHAR(12),
                        failure_type VARCHAR(64),
                        idempotency_key VARCHAR(255) NOT NULL,
                        request_fingerprint VARCHAR NOT NULL,
                        remote_run_id VARCHAR,
                        start_idempotency_key VARCHAR(255),
                        cancel_requested_at DATETIME,
                        deadline_at DATETIME,
                        last_polled_at DATETIME,
                        version INTEGER NOT NULL,
                        created_at DATETIME NOT NULL,
                        started_at DATETIME,
                        finished_at DATETIME,
                        CONSTRAINT unique_script_version_idempotency_key
                            UNIQUE (script_version_id, idempotency_key),
                        FOREIGN KEY(case_id) REFERENCES test_cases (id),
                        FOREIGN KEY(script_version_id) REFERENCES script_versions (id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE task_runner_configs (
                        task_id VARCHAR(40) NOT NULL PRIMARY KEY,
                        config_snapshot JSON NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks (id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE pod_leases (
                        pod_id VARCHAR(255) NOT NULL PRIMARY KEY,
                        task_id VARCHAR(40) NOT NULL UNIQUE,
                        worker_id VARCHAR(255) NOT NULL,
                        expires_at DATETIME NOT NULL,
                        version INTEGER NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks (id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO test_cases (
                        id, title, content_markdown, tags, automation_level,
                        created_by, created_at, updated_at
                    )
                    VALUES (
                        'case_legacy', '历史用例', '- 打开应用', '[]', 'auto',
                        'admin', :now, :now
                    )
                    """
                ),
                {"now": now},
            )
            connection.execute(
                text("INSERT INTO script_versions (id) VALUES ('script_legacy')")
            )
            connection.execute(
                text(
                    """
                    INSERT INTO tasks (
                        id, case_id, script_version_id, runner_type, scenario,
                        execution_status, idempotency_key, request_fingerprint,
                        version, created_at
                    )
                    VALUES (
                        'task_legacy', 'case_legacy', 'script_legacy', 'mock',
                        '历史用例', 'result_ready', 'legacy-key', '{}', 1, :now
                    )
                    """
                ),
                {"now": now},
            )
            connection.execute(
                text(
                    "INSERT INTO task_runner_configs (task_id, config_snapshot) "
                    "VALUES ('task_legacy', '{\"pod_id\":\"mock:default\"}')"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pod_leases (
                        pod_id, task_id, worker_id, expires_at, version
                    )
                    VALUES (
                        'legacy:pod', 'task_legacy', 'worker-legacy', :now, 1
                    )
                    """
                ),
                {"now": now},
            )

        ensure_schema_migrations(engine)

        task_columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("tasks")
        }
        assert task_columns["script_version_id"]["nullable"] is True
        task_foreign_keys = inspect(engine).get_foreign_keys("tasks")
        assert all(
            foreign_key["referred_table"] != "script_versions"
            for foreign_key in task_foreign_keys
        )

        with engine.begin() as connection:
            preserved = connection.execute(
                text(
                    "SELECT case_id, script_version_id FROM tasks "
                    "WHERE id = 'task_legacy'"
                )
            ).one()
            assert preserved == ("case_legacy", "script_legacy")
            assert connection.execute(
                text(
                    "SELECT task_id FROM task_runner_configs "
                    "WHERE task_id = 'task_legacy'"
                )
            ).scalar_one() == "task_legacy"
            assert connection.execute(
                text(
                    "SELECT task_id FROM pod_leases "
                    "WHERE task_id = 'task_legacy'"
                )
            ).scalar_one() == "task_legacy"

            connection.execute(
                text(
                    """
                    INSERT INTO tasks (
                        id, case_id, script_version_id, runner_type, scenario,
                        execution_status, idempotency_key, request_fingerprint,
                        version, created_at, prompt_snapshot, created_by
                    )
                    VALUES (
                        'task_current', 'case_legacy', NULL, 'mobile_use',
                        '当前用例', 'queued', 'current-key', '{}', 1, :now,
                        '- 打开应用', 'admin'
                    )
                    """
                ),
                {"now": now},
            )
            connection.execute(
                text(
                    "INSERT INTO task_runner_configs (task_id, config_snapshot) "
                    "VALUES ('task_current', '{\"pod_id\":\"pod_current\"}')"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pod_leases (
                        pod_id, task_id, worker_id, expires_at, version
                    )
                    VALUES (
                        'product:pod_current', 'task_current', 'reserved', :now, 1
                    )
                    """
                ),
                {"now": now},
            )
            assert connection.execute(
                text("PRAGMA foreign_key_check")
            ).all() == []
    finally:
        engine.dispose()


def test_batch_schema_is_added_without_rebuilding_current_tasks():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL PRIMARY KEY
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE tasks (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        case_id VARCHAR(40) NOT NULL,
                        script_version_id VARCHAR(40),
                        runner_type VARCHAR(32) NOT NULL,
                        scenario VARCHAR(32) NOT NULL,
                        execution_status VARCHAR(15) NOT NULL,
                        verdict VARCHAR(12),
                        failure_type VARCHAR(64),
                        idempotency_key VARCHAR(255) NOT NULL,
                        request_fingerprint VARCHAR NOT NULL,
                        version INTEGER NOT NULL,
                        created_at DATETIME NOT NULL,
                        FOREIGN KEY(case_id) REFERENCES test_cases (id)
                    )
                    """
                )
            )

        Base.metadata.create_all(engine)
        ensure_schema_migrations(engine)

        tables = set(inspect(engine).get_table_names())
        columns = {
            column["name"] for column in inspect(engine).get_columns("tasks")
        }
        assert "task_batches" in tables
        assert {"batch_id", "batch_position", "queue_reason"} <= columns
    finally:
        engine.dispose()


def test_test_plan_schema_and_tag_registry_are_added():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        tags JSON DEFAULT '[]'
                    )
                    """
                )
            )

        assert set(inspect(engine).get_table_names()) == {"test_cases"}

        ensure_schema_migrations(engine)

        tables = set(inspect(engine).get_table_names())
        assert {
            "test_plans",
            "test_plan_cases",
            "plan_executions",
            "tag_color_registry",
        } <= tables

        indexes = {
            index["name"]: index
            for index in inspect(engine).get_indexes("test_plans")
        }
        active_name_index = indexes["uq_active_test_plan_name_key"]
        assert active_name_index["unique"] == 1
        assert str(active_name_index["dialect_options"]["sqlite_where"]) == (
            "deleted_at IS NULL"
        )
    finally:
        engine.dispose()


def test_existing_test_plans_receive_default_test_type():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_plans (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        name_key VARCHAR(100) NOT NULL,
                        description TEXT,
                        tags JSON DEFAULT '[]',
                        created_by VARCHAR(100) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        deleted_at DATETIME
                    )
                    """
                )
            )
            now = datetime(2026, 7, 30, 0, 0, tzinfo=UTC)
            connection.execute(
                text(
                    """
                    INSERT INTO test_plans (
                        id, name, name_key, description, tags, created_by,
                        created_at, updated_at, deleted_at
                    )
                    VALUES (
                        'plan_legacy', '旧计划', '旧计划', NULL, '[]',
                        'admin', :now, :now, NULL
                    )
                    """
                ),
                {"now": now},
            )

        ensure_schema_migrations(engine)

        columns = {
            column["name"]
            for column in inspect(engine).get_columns("test_plans")
        }
        assert "test_type" in columns
        with engine.connect() as connection:
            value = connection.execute(
                text("SELECT test_type FROM test_plans WHERE id = 'plan_legacy'")
            ).scalar_one()
        assert value == "regression"
    finally:
        engine.dispose()


def test_existing_case_tags_receive_unique_registered_colors():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                CaseModel(
                    id="case_a",
                    title="A",
                    content_markdown="- A",
                    tags=["smoke", "P0"],
                ),
                CaseModel(
                    id="case_b",
                    title="B",
                    content_markdown="- B",
                    tags=["smoke", "核心链路"],
                ),
            ]
        )
        db.commit()
    ensure_schema_migrations(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT tag_name, foreground_color, background_color "
                "FROM tag_color_registry ORDER BY tag_name"
            )
        ).all()
    assert [row.tag_name for row in rows] == ["P0", "smoke", "核心链路"]
    assert len({row.foreground_color for row in rows}) == 3
    assert all(
        row.background_color.startswith(row.foreground_color)
        and row.background_color.endswith("1A")
        for row in rows
    )


def test_active_plan_name_is_unique_and_can_be_reused_after_soft_delete():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        ensure_schema_migrations(engine)
        with engine.begin() as connection:
            _insert_test_plan(
                connection,
                plan_id="plan_original",
                name="冒烟计划",
                name_key="冒烟计划",
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_test_plan(
                    connection,
                    plan_id="plan_duplicate",
                    name="冒烟计划",
                    name_key="冒烟计划",
                )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE test_plans SET deleted_at = :deleted_at "
                    "WHERE id = 'plan_original'"
                ),
                {"deleted_at": datetime(2026, 7, 30, 1, 0, tzinfo=UTC)},
            )
            _insert_test_plan(
                connection,
                plan_id="plan_reused",
                name="冒烟计划",
                name_key="冒烟计划",
            )

        with engine.connect() as connection:
            active_ids = connection.execute(
                text(
                    "SELECT id FROM test_plans "
                    "WHERE name_key = '冒烟计划' AND deleted_at IS NULL"
                )
            ).scalars()
            assert list(active_ids) == ["plan_reused"]
    finally:
        engine.dispose()


def test_plan_case_requires_unique_case_and_position_within_plan():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        ensure_schema_migrations(engine)
        with engine.begin() as connection:
            _insert_test_plan(
                connection,
                plan_id="plan_unique_cases",
                name="唯一性计划",
                name_key="唯一性计划",
            )
            _insert_test_case(connection, "case_one")
            _insert_test_case(connection, "case_two")
            connection.execute(
                text(
                    "INSERT INTO test_plan_cases (plan_id, case_id, position) "
                    "VALUES ('plan_unique_cases', 'case_one', 1)"
                )
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO test_plan_cases (plan_id, case_id, position) "
                        "VALUES ('plan_unique_cases', 'case_one', 2)"
                    )
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO test_plan_cases (plan_id, case_id, position) "
                        "VALUES ('plan_unique_cases', 'case_two', 1)"
                    )
                )
    finally:
        engine.dispose()


def test_plan_case_plan_foreign_key_is_enforced_when_case_exists():
    engine = _create_migrated_foreign_key_engine()
    try:
        with engine.begin() as connection:
            _insert_test_case(connection, "case_existing")

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO test_plan_cases (plan_id, case_id, position) "
                        "VALUES ('missing_plan', 'case_existing', 1)"
                    )
                )
    finally:
        engine.dispose()


def test_plan_case_case_foreign_key_is_enforced_when_plan_exists():
    engine = _create_migrated_foreign_key_engine()
    try:
        with engine.begin() as connection:
            _insert_test_plan(
                connection,
                plan_id="plan_existing",
                name="已存在计划",
                name_key="已存在计划",
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO test_plan_cases (plan_id, case_id, position) "
                        "VALUES ('plan_existing', 'missing_case', 1)"
                    )
                )
    finally:
        engine.dispose()


def test_plan_execution_plan_foreign_key_is_enforced_when_batch_exists():
    engine = _create_migrated_foreign_key_engine()
    try:
        with engine.begin() as connection:
            _insert_task_batch(connection, "batch_existing")

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_plan_execution(
                    connection,
                    execution_id="execution_missing_plan",
                    plan_id="missing_plan",
                    batch_id="batch_existing",
                )
    finally:
        engine.dispose()


def test_plan_execution_batch_foreign_key_is_enforced_when_plan_exists():
    engine = _create_migrated_foreign_key_engine()
    try:
        with engine.begin() as connection:
            _insert_test_plan(
                connection,
                plan_id="plan_existing",
                name="已存在计划",
                name_key="已存在计划",
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_plan_execution(
                    connection,
                    execution_id="execution_missing_batch",
                    plan_id="plan_existing",
                    batch_id="missing_batch",
                )
    finally:
        engine.dispose()


def test_plan_execution_task_batch_is_unique_when_dependencies_exist():
    engine = _create_migrated_foreign_key_engine()
    try:
        with engine.begin() as connection:
            _insert_test_plan(
                connection,
                plan_id="plan_existing",
                name="已存在计划",
                name_key="已存在计划",
            )
            _insert_task_batch(connection, "batch_existing")
            _insert_plan_execution(
                connection,
                execution_id="execution_original",
                plan_id="plan_existing",
                batch_id="batch_existing",
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_plan_execution(
                    connection,
                    execution_id="execution_duplicate",
                    plan_id="plan_existing",
                    batch_id="batch_existing",
                )
    finally:
        engine.dispose()


def test_tag_migration_is_idempotent_and_preserves_existing_registration():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            _insert_test_case(connection, "case_tags")
            connection.execute(
                text(
                    "UPDATE test_cases SET tags = "
                    "'[\"registered\", \"new-tag\"]' WHERE id = 'case_tags'"
                )
            )
            connection.execute(
                TagColorRegistry.__table__.insert(),
                {
                    "tag_name": "registered",
                    "foreground_color": "#334455",
                    "background_color": "#3344551A",
                    "created_at": datetime(2026, 7, 30, 0, 0, tzinfo=UTC),
                },
            )

        ensure_schema_migrations(engine)
        with engine.connect() as connection:
            first_rows = connection.execute(
                text(
                    "SELECT tag_name, foreground_color, background_color "
                    "FROM tag_color_registry ORDER BY tag_name"
                )
            ).all()

        ensure_schema_migrations(engine)
        with engine.connect() as connection:
            second_rows = connection.execute(
                text(
                    "SELECT tag_name, foreground_color, background_color "
                    "FROM tag_color_registry ORDER BY tag_name"
                )
            ).all()

        assert second_rows == first_rows
        assert dict((row.tag_name, row.foreground_color) for row in second_rows)[
            "registered"
        ] == "#334455"
    finally:
        engine.dispose()


def test_tag_color_collision_advances_to_next_available_color():
    engine = create_engine("sqlite://")
    tag_name = "collision-target"
    first_color = _unused_tag_color(tag_name, set())
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            _insert_test_case(connection, "case_collision")
            connection.execute(
                text(
                    "UPDATE test_cases SET tags = "
                    "'[\"collision-target\"]' WHERE id = 'case_collision'"
                )
            )
            connection.execute(
                TagColorRegistry.__table__.insert(),
                {
                    "tag_name": "occupied",
                    "foreground_color": first_color,
                    "background_color": f"{first_color}1A",
                    "created_at": datetime(2026, 7, 30, 0, 0, tzinfo=UTC),
                },
            )

        ensure_schema_migrations(engine)

        with engine.connect() as connection:
            assigned = connection.execute(
                text(
                    "SELECT foreground_color FROM tag_color_registry "
                    "WHERE tag_name = :tag_name"
                ),
                {"tag_name": tag_name},
            ).scalar_one()
        assert assigned == _unused_tag_color(tag_name, {first_color})
        assert assigned != first_color
    finally:
        engine.dispose()


def test_invalid_case_tag_json_does_not_block_valid_tag_backfill():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        tags JSON
                    )
                    """
                )
            )
            connection.execute(
                text("INSERT INTO test_cases (id, title, tags) VALUES (:id, :id, :tags)"),
                [
                    {"id": "null_tags", "tags": None},
                    {"id": "invalid_json", "tags": "{not-json"},
                    {"id": "json_object", "tags": '{"tag":"ignored"}'},
                    {"id": "json_string", "tags": '"ignored"'},
                    {
                        "id": "mixed_array",
                        "tags": '[1, "good", null, {}, "also-valid"]',
                    },
                    {"id": "valid_array", "tags": '["other"]'},
                ],
            )

        ensure_schema_migrations(engine)

        with engine.connect() as connection:
            tag_names = connection.execute(
                text("SELECT tag_name FROM tag_color_registry ORDER BY tag_name")
            ).scalars()
            assert list(tag_names) == ["also-valid", "good", "other"]
    finally:
        engine.dispose()


def test_non_utf8_case_tag_does_not_block_valid_tag_backfill():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        tags JSON
                    )
                    """
                )
            )
            connection.execute(
                text("INSERT INTO test_cases (id, title, tags) VALUES (:id, :id, :tags)"),
                {"id": "surrogate_tag", "tags": r'["\ud800", "smoke"]'},
            )

        ensure_schema_migrations(engine)

        with engine.connect() as connection:
            tag_names = connection.execute(
                text("SELECT tag_name FROM tag_color_registry ORDER BY tag_name")
            ).scalars()
            assert list(tag_names) == ["smoke"]
    finally:
        engine.dispose()


def test_blank_case_tags_are_skipped_during_tag_backfill():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE test_cases (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        tags JSON
                    )
                    """
                )
            )
            connection.execute(
                text("INSERT INTO test_cases (id, title, tags) VALUES (:id, :id, :tags)"),
                {"id": "blank_tags", "tags": '["", "   ", "smoke"]'},
            )

        ensure_schema_migrations(engine)

        with engine.connect() as connection:
            tag_names = connection.execute(
                text("SELECT tag_name FROM tag_color_registry ORDER BY tag_name")
            ).scalars()
            assert list(tag_names) == ["smoke"]
    finally:
        engine.dispose()


def test_generated_tag_colors_are_restricted_and_accessible_on_white():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(
                CaseModel(
                    id="case_color_space",
                    title="Color Space",
                    content_markdown="- colors",
                    tags=[f"generated-{index}" for index in range(128)],
                )
            )
            db.commit()

        ensure_schema_migrations(engine)

        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT foreground_color, background_color "
                    "FROM tag_color_registry"
                )
            ).all()

        assert len(rows) == 128
        assert len({row.foreground_color for row in rows}) == 128
        for row in rows:
            foreground = row.foreground_color
            rgb = tuple(
                int(foreground[index : index + 2], 16) / 255
                for index in (1, 3, 5)
            )
            saturation = colorsys.rgb_to_hls(*rgb)[2]
            assert saturation <= 0.50
            assert _contrast_ratio(foreground, "#FFFFFF") >= 4.5
            assert (
                _contrast_ratio(foreground, _composite_over_white(foreground))
                >= 4.5
            )
            assert row.background_color[:7] == foreground
            assert 0.09 <= int(row.background_color[7:], 16) / 255 <= 0.11
    finally:
        engine.dispose()


def test_every_tag_color_candidate_contrasts_with_its_composited_background():
    risky_color = "#79792A"
    assert _contrast_ratio(risky_color, "#FFFFFF") >= 4.5
    assert _contrast_ratio(
        risky_color,
        _composite_over_white(risky_color),
    ) < 4.5

    assert risky_color not in _TAG_COLOR_CANDIDATES
    assert all(
        _contrast_ratio(color, _composite_over_white(color)) >= 4.5
        for color in _TAG_COLOR_CANDIDATES
    )


def test_schedule_tables_exist_after_migration():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        ensure_schema_migrations(engine)

        tables = set(inspect(engine).get_table_names())
        assert "test_plan_schedules" in tables
        assert "schedule_events" in tables

        schedule_columns = {
            col["name"]
            for col in inspect(engine).get_columns("test_plan_schedules")
        }
        assert {
            "id", "business_id", "test_plan_id", "cron_expr", "timezone",
            "enabled", "next_run_at", "last_run_at", "last_skip_reason",
            "execution_config", "created_by", "created_at", "updated_at",
        }.issubset(schedule_columns)

        event_columns = {
            col["name"]
            for col in inspect(engine).get_columns("schedule_events")
        }
        assert {
            "id", "schedule_id", "business_id", "event_type", "trigger_type",
            "scheduled_for", "fired_at", "plan_execution_id",
            "skip_reason", "error_message", "created_at",
        }.issubset(event_columns)

        indexes = {
            idx["name"]
            for idx in inspect(engine).get_indexes("test_plan_schedules")
        }
        assert "ix_schedule_enabled_next_run" in indexes

        fks = inspect(engine).get_foreign_keys("schedule_events")
        assert any(fk["referred_table"] == "test_plan_schedules" for fk in fks)
    finally:
        engine.dispose()
