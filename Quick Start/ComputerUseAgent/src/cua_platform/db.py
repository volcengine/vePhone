import colorsys
import json
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from cua_platform.config import Settings


class Base(DeclarativeBase):
    pass


def create_engine_and_session(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine, sessionmaker(engine, expire_on_commit=False)


def database_is_ready(engine: Engine) -> bool:
    with engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1


def ensure_auth_session_activity_column(engine: Engine) -> None:
    columns = {
        column["name"] for column in inspect(engine).get_columns("auth_sessions")
    }
    if "last_seen_at" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN last_seen_at DATETIME"))
        connection.execute(
            text("UPDATE auth_sessions SET last_seen_at = created_at WHERE last_seen_at IS NULL")
        )


def ensure_users_multi_account_schema(engine: Engine) -> None:
    if not _table_exists(engine, "users"):
        return
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("users")}
    check_constraints = inspector.get_check_constraints("users")
    has_single_admin_constraint = any(
        constraint.get("name") == "single_admin_id"
        or "id = 1" in (constraint.get("sqltext") or "")
        for constraint in check_constraints
    )
    required_columns = {
        "display_name",
        "email",
        "role",
        "status",
        "last_login_at",
        "updated_at",
    }
    if required_columns.issubset(columns) and not has_single_admin_constraint:
        return

    def expr(column: str, fallback: str) -> str:
        return column if column in columns else fallback

    connection = engine.connect()
    try:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        with connection.begin():
            connection.execute(
                text(
                    """
                    CREATE TABLE users_current (
                        id INTEGER NOT NULL PRIMARY KEY,
                        username VARCHAR(64) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        display_name VARCHAR(100),
                        email VARCHAR(255),
                        role VARCHAR(32) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        last_login_at DATETIME,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    INSERT INTO users_current (
                        id, username, password_hash, display_name, email,
                        role, status, last_login_at, created_at, updated_at
                    )
                    SELECT
                        id,
                        username,
                        password_hash,
                        {expr('display_name', 'NULL')},
                        {expr('email', 'NULL')},
                        COALESCE({expr('role', "'admin'")}, 'admin'),
                        COALESCE({expr('status', "'active'")}, 'active'),
                        {expr('last_login_at', 'NULL')},
                        COALESCE({expr('created_at', 'CURRENT_TIMESTAMP')}, CURRENT_TIMESTAMP),
                        COALESCE({expr('updated_at', expr('created_at', 'CURRENT_TIMESTAMP'))}, CURRENT_TIMESTAMP)
                    FROM users
                    """
                )
            )
            connection.execute(text("DROP TABLE users"))
            connection.execute(text("ALTER TABLE users_current RENAME TO users"))
            connection.execute(
                text("CREATE UNIQUE INDEX ix_users_username ON users (username)")
            )
    finally:
        try:
            if connection.in_transaction():
                connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
        finally:
            connection.close()


def _column_exists(engine: Engine, table: str, column: str) -> bool:
    columns = {c["name"] for c in inspect(engine).get_columns(table)}
    return column in columns


def _table_exists(engine: Engine, table: str) -> bool:
    return table in inspect(engine).get_table_names()


_TAG_COLOR_SATURATIONS = (0.24, 0.30, 0.36, 0.42, 0.48)
_TAG_COLOR_LIGHTNESSES = (0.24, 0.28, 0.32)
_TAG_COLOR_HUE_STEPS = 720
_TAG_BACKGROUND_ALPHA = 0x1A / 255
_MIN_TAG_CONTRAST_RATIO = 4.5


def _linearized_channel(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _tag_color_contrast_ratio(red: int, green: int, blue: int) -> float:
    foreground_channels = tuple(channel / 255 for channel in (red, green, blue))
    background_channels = tuple(
        channel * _TAG_BACKGROUND_ALPHA + 1 * (1 - _TAG_BACKGROUND_ALPHA)
        for channel in foreground_channels
    )
    foreground_luminance = (
        0.2126 * _linearized_channel(foreground_channels[0])
        + 0.7152 * _linearized_channel(foreground_channels[1])
        + 0.0722 * _linearized_channel(foreground_channels[2])
    )
    background_luminance = (
        0.2126 * _linearized_channel(background_channels[0])
        + 0.7152 * _linearized_channel(background_channels[1])
        + 0.0722 * _linearized_channel(background_channels[2])
    )
    return (background_luminance + 0.05) / (foreground_luminance + 0.05)


def _build_tag_color_candidates() -> tuple[str, ...]:
    candidates = []
    seen = set()
    for lightness in _TAG_COLOR_LIGHTNESSES:
        for saturation in _TAG_COLOR_SATURATIONS:
            for hue_step in range(_TAG_COLOR_HUE_STEPS):
                red, green, blue = (
                    round(channel * 255)
                    for channel in colorsys.hls_to_rgb(
                        hue_step / _TAG_COLOR_HUE_STEPS,
                        lightness,
                        saturation,
                    )
                )
                color = f"#{red:02X}{green:02X}{blue:02X}"
                if (
                    color not in seen
                    and _tag_color_contrast_ratio(red, green, blue)
                    >= _MIN_TAG_CONTRAST_RATIO
                ):
                    seen.add(color)
                    candidates.append(color)
    return tuple(candidates)


_TAG_COLOR_CANDIDATES = _build_tag_color_candidates()


def _unused_tag_color(tag_name: str, used_colors: set[str]) -> str:
    seed = int.from_bytes(sha256(tag_name.encode("utf-8")).digest()[:8], "big")
    for offset in range(len(_TAG_COLOR_CANDIDATES)):
        color = _TAG_COLOR_CANDIDATES[
            (seed + offset) % len(_TAG_COLOR_CANDIDATES)
        ]
        if color not in used_colors:
            return color
    raise RuntimeError("tag color registry exhausted")


def _case_tag_names(connection) -> set[str]:
    tag_names = set()
    raw_case_tags = connection.execute(text("SELECT tags FROM test_cases")).scalars()
    for raw_tags in raw_case_tags:
        if raw_tags is None:
            continue
        try:
            tags = json.loads(raw_tags) if isinstance(raw_tags, (str, bytes)) else raw_tags
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            continue
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                continue
            try:
                tag.encode("utf-8")
            except UnicodeEncodeError:
                continue
            tag_names.add(tag)
    return tag_names


def _register_existing_case_tags(engine: Engine) -> None:
    from cua_platform.test_plans.models import TagColorRegistry, utc_now

    if not _table_exists(engine, "test_cases"):
        return

    with engine.begin() as connection:
        existing_rows = connection.execute(
            text(
                "SELECT tag_name, foreground_color "
                "FROM tag_color_registry"
            )
        ).all()
        registered_tags = {row.tag_name for row in existing_rows}
        used_colors = {row.foreground_color for row in existing_rows}
        tag_names = sorted(_case_tag_names(connection))

        rows = []
        for tag_name in tag_names:
            if tag_name in registered_tags:
                continue
            foreground_color = _unused_tag_color(tag_name, used_colors)
            used_colors.add(foreground_color)
            rows.append(
                {
                    "tag_name": tag_name,
                    "foreground_color": foreground_color,
                    "background_color": f"{foreground_color}1A",
                    "created_at": utc_now(),
                }
            )
        if rows:
            connection.execute(TagColorRegistry.__table__.insert(), rows)


def _tasks_require_current_schema(engine: Engine) -> bool:
    columns = {
        column["name"]: column for column in inspect(engine).get_columns("tasks")
    }
    script_column = columns.get("script_version_id")
    if script_column is None or not script_column["nullable"]:
        return True
    return any(
        foreign_key["referred_table"] == "script_versions"
        for foreign_key in inspect(engine).get_foreign_keys("tasks")
    )


def _rebuild_tasks_for_current_schema(engine: Engine) -> None:
    connection = engine.connect()
    try:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        with connection.begin():
            connection.execute(
                text(
                    """
                    CREATE TABLE tasks_current (
                        id VARCHAR(40) NOT NULL PRIMARY KEY,
                        business_id VARCHAR(40) DEFAULT 'biz_default',
                        case_id VARCHAR(40) NOT NULL,
                        batch_id VARCHAR(40),
                        batch_position INTEGER,
                        queue_reason VARCHAR(64),
                        script_version_id VARCHAR(40),
                        prompt_snapshot TEXT,
                        result_summary TEXT,
                        result_evidence JSON DEFAULT '[]',
                        runner_type VARCHAR(32) NOT NULL,
                        scenario VARCHAR(32) NOT NULL,
                        created_by VARCHAR(100) DEFAULT 'system',
                        execution_status VARCHAR(15) NOT NULL,
                        verdict VARCHAR(12),
                        review_result VARCHAR(12),
                        reviewed_by VARCHAR(100),
                        reviewed_at DATETIME,
                        review_note TEXT,
                        failure_type VARCHAR(64),
                        idempotency_key VARCHAR(255) NOT NULL,
                        request_fingerprint VARCHAR NOT NULL,
                        remote_run_id VARCHAR,
                        remote_thread_id VARCHAR,
                        remote_status_code INTEGER,
                        remote_step_id VARCHAR,
                        recording_url TEXT,
                        result_assets JSON DEFAULT '{}',
                        start_idempotency_key VARCHAR(255),
                        start_state VARCHAR(11) NOT NULL DEFAULT 'pending',
                        start_attempted_at DATETIME,
                        cancel_requested_at DATETIME,
                        deadline_at DATETIME,
                        last_polled_at DATETIME,
                        version INTEGER NOT NULL,
                        created_at DATETIME NOT NULL,
                        started_at DATETIME,
                        finished_at DATETIME,
                        FOREIGN KEY(case_id) REFERENCES test_cases (id),
                        FOREIGN KEY(batch_id) REFERENCES task_batches (id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO tasks_current (
                        id, business_id, case_id, batch_id, batch_position, queue_reason,
                        script_version_id, prompt_snapshot,
                        result_summary, result_evidence, runner_type, scenario,
                        created_by, execution_status, verdict,
                        review_result, reviewed_by, reviewed_at, review_note,
                        failure_type,
                        idempotency_key, request_fingerprint, remote_run_id,
                        remote_thread_id, remote_status_code, remote_step_id,
                        recording_url, result_assets, start_idempotency_key,
                        start_state, start_attempted_at, cancel_requested_at,
                        deadline_at, last_polled_at, version, created_at,
                        started_at, finished_at
                    )
                    SELECT
                        id,
                        COALESCE(business_id, 'biz_default'),
                        case_id, batch_id, batch_position, queue_reason,
                        script_version_id, prompt_snapshot,
                        result_summary, COALESCE(result_evidence, '[]'),
                        runner_type, scenario, COALESCE(created_by, 'system'),
                        execution_status, verdict,
                        NULL, NULL, NULL, NULL,
                        failure_type,
                        idempotency_key, request_fingerprint, remote_run_id,
                        remote_thread_id, remote_status_code, remote_step_id,
                        recording_url, COALESCE(result_assets, '{}'),
                        start_idempotency_key, start_state, start_attempted_at,
                        cancel_requested_at, deadline_at, last_polled_at, version,
                        created_at, started_at, finished_at
                    FROM tasks
                    """
                )
            )
            connection.execute(text("DROP TABLE tasks"))
            connection.execute(text("ALTER TABLE tasks_current RENAME TO tasks"))
            connection.execute(text("CREATE INDEX ix_tasks_business_id ON tasks (business_id)"))
            connection.execute(text("CREATE INDEX ix_tasks_case_id ON tasks (case_id)"))
            connection.execute(text("CREATE INDEX ix_tasks_batch_id ON tasks (batch_id)"))
            connection.execute(
                text(
                    "CREATE INDEX ix_tasks_script_version_id "
                    "ON tasks (script_version_id)"
                )
            )
    finally:
        try:
            if connection.in_transaction():
                connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
        finally:
            connection.close()


def ensure_schema_migrations(engine: Engine) -> None:
    from sqlalchemy import text as sql_text
    from cua_platform.business.models import (
        DEFAULT_BUSINESS_ID,
        DEFAULT_BUSINESS_NAME,
        BusinessSpace,
    )
    from cua_platform.business.service import business_name_key
    from cua_platform.tasks.models import TaskBatch
    from cua_platform.test_plans.models import (
        PlanExecution,
        ScheduleEvent,
        TagColorRegistry,
        TestPlan,
        TestPlanCase,
        TestPlanSchedule,
    )

    BusinessSpace.__table__.create(engine, checkfirst=True)
    TaskBatch.__table__.create(engine, checkfirst=True)
    ensure_users_multi_account_schema(engine)
    if not _column_exists(engine, "business_spaces", "task_concurrency_limit"):
        with engine.begin() as connection:
            connection.execute(
                sql_text(
                    "ALTER TABLE business_spaces ADD COLUMN "
                    "task_concurrency_limit INTEGER NOT NULL DEFAULT 4"
                )
            )
    with engine.begin() as connection:
        existing_default = connection.execute(
            sql_text("SELECT id FROM business_spaces WHERE id = :id"),
            {"id": DEFAULT_BUSINESS_ID},
        ).first()
        if existing_default is None:
            connection.execute(
                BusinessSpace.__table__.insert().values(
                    id=DEFAULT_BUSINESS_ID,
                    name=DEFAULT_BUSINESS_NAME,
                    name_key=business_name_key(DEFAULT_BUSINESS_NAME),
                    description=None,
                    is_default=True,
                    created_by="system",
                )
            )

    if _table_exists(engine, "test_cases"):
        alterations = [
            ("business_id", "ALTER TABLE test_cases ADD COLUMN business_id VARCHAR(40) DEFAULT 'biz_default'"),
            ("module", "ALTER TABLE test_cases ADD COLUMN module VARCHAR(100)"),
            ("content_markdown", "ALTER TABLE test_cases ADD COLUMN content_markdown TEXT"),
            ("tags", "ALTER TABLE test_cases ADD COLUMN tags JSON DEFAULT '[]'"),
            ("automation_level", "ALTER TABLE test_cases ADD COLUMN automation_level VARCHAR(32) DEFAULT 'manual_confirm'"),
            ("default_agent_options", "ALTER TABLE test_cases ADD COLUMN default_agent_options JSON"),
            ("execution_count", "ALTER TABLE test_cases ADD COLUMN execution_count INTEGER DEFAULT 0"),
            ("pass_count", "ALTER TABLE test_cases ADD COLUMN pass_count INTEGER DEFAULT 0"),
            ("fail_count", "ALTER TABLE test_cases ADD COLUMN fail_count INTEGER DEFAULT 0"),
            ("last_executed_at", "ALTER TABLE test_cases ADD COLUMN last_executed_at DATETIME"),
            ("created_by", "ALTER TABLE test_cases ADD COLUMN created_by VARCHAR(100) DEFAULT 'system'"),
            ("created_at", "ALTER TABLE test_cases ADD COLUMN created_at DATETIME"),
            ("updated_at", "ALTER TABLE test_cases ADD COLUMN updated_at DATETIME"),
            ("deleted_at", "ALTER TABLE test_cases ADD COLUMN deleted_at DATETIME"),
        ]
        with engine.begin() as connection:
            for col_name, ddl in alterations:
                if not _column_exists(engine, "test_cases", col_name):
                    connection.execute(sql_text(ddl))
            connection.execute(
                sql_text(
                    "UPDATE test_cases SET business_id = 'biz_default' "
                    "WHERE business_id IS NULL OR business_id = ''"
                )
            )
            for col_name in (
                "mode",
                "app_name",
                "app_version",
                "preconditions",
                "steps",
                "assertions",
                "mock_scenario",
            ):
                if _column_exists(engine, "test_cases", col_name):
                    connection.execute(
                        sql_text(f"ALTER TABLE test_cases DROP COLUMN {col_name}")
                    )

    if _table_exists(engine, "tasks"):
        added_start_state = not _column_exists(engine, "tasks", "start_state")
        task_alterations = [
            ("business_id", "ALTER TABLE tasks ADD COLUMN business_id VARCHAR(40) DEFAULT 'biz_default'"),
            ("batch_id", "ALTER TABLE tasks ADD COLUMN batch_id VARCHAR(40)"),
            ("batch_position", "ALTER TABLE tasks ADD COLUMN batch_position INTEGER"),
            ("queue_reason", "ALTER TABLE tasks ADD COLUMN queue_reason VARCHAR(64)"),
            ("prompt_snapshot", "ALTER TABLE tasks ADD COLUMN prompt_snapshot TEXT"),
            ("result_summary", "ALTER TABLE tasks ADD COLUMN result_summary TEXT"),
            ("result_evidence", "ALTER TABLE tasks ADD COLUMN result_evidence JSON DEFAULT '[]'"),
            ("remote_thread_id", "ALTER TABLE tasks ADD COLUMN remote_thread_id VARCHAR"),
            ("remote_status_code", "ALTER TABLE tasks ADD COLUMN remote_status_code INTEGER"),
            ("remote_step_id", "ALTER TABLE tasks ADD COLUMN remote_step_id VARCHAR"),
            ("recording_url", "ALTER TABLE tasks ADD COLUMN recording_url TEXT"),
            ("result_assets", "ALTER TABLE tasks ADD COLUMN result_assets JSON DEFAULT '{}'"),
            ("start_state", "ALTER TABLE tasks ADD COLUMN start_state VARCHAR(11) NOT NULL DEFAULT 'pending'"),
            ("start_attempted_at", "ALTER TABLE tasks ADD COLUMN start_attempted_at DATETIME"),
            ("created_by", "ALTER TABLE tasks ADD COLUMN created_by VARCHAR(100) DEFAULT 'system'"),
            ("review_result", "ALTER TABLE tasks ADD COLUMN review_result VARCHAR(12)"),
            ("reviewed_by", "ALTER TABLE tasks ADD COLUMN reviewed_by VARCHAR(100)"),
            ("reviewed_at", "ALTER TABLE tasks ADD COLUMN reviewed_at DATETIME"),
            ("review_note", "ALTER TABLE tasks ADD COLUMN review_note TEXT"),
        ]
        with engine.begin() as connection:
            for col_name, ddl in task_alterations:
                if not _column_exists(engine, "tasks", col_name):
                    connection.execute(sql_text(ddl))
            if added_start_state:
                attached_condition = (
                    "remote_run_id IS NOT NULL"
                    if _column_exists(engine, "tasks", "remote_run_id")
                    else "0"
                )
                connection.execute(
                    sql_text(
                        f"""
                        UPDATE tasks
                        SET start_state = CASE
                            WHEN {attached_condition} THEN 'attached'
                            WHEN execution_status = 'running' THEN 'dispatching'
                            ELSE 'pending'
                        END
                        """
                    )
                )
            connection.execute(
                sql_text(
                    "UPDATE tasks SET business_id = 'biz_default' "
                    "WHERE business_id IS NULL OR business_id = ''"
                )
            )
            connection.execute(
                sql_text(
                    "UPDATE tasks SET created_by = 'system' "
                    "WHERE created_by IS NULL OR created_by = ''"
                )
            )
            connection.execute(
                sql_text(
                    "UPDATE tasks SET execution_status = 'result_ready', verdict = 'fail' "
                    "WHERE execution_status = 'review_required'"
                )
            )
            connection.execute(
                sql_text(
                    "UPDATE tasks SET verdict = 'fail' WHERE verdict = 'inconclusive'"
                )
            )
        if _tasks_require_current_schema(engine):
            _rebuild_tasks_for_current_schema(engine)

    if _table_exists(engine, "task_batches"):
        with engine.begin() as connection:
            if not _column_exists(engine, "task_batches", "business_id"):
                connection.execute(
                    sql_text(
                        "ALTER TABLE task_batches ADD COLUMN "
                        "business_id VARCHAR(40) DEFAULT 'biz_default'"
                    )
                )
            connection.execute(
                sql_text(
                    "UPDATE task_batches SET business_id = 'biz_default' "
                    "WHERE business_id IS NULL OR business_id = ''"
                )
            )

    if _table_exists(engine, "test_plans"):
        with engine.begin() as connection:
            if not _column_exists(engine, "test_plans", "business_id"):
                connection.execute(
                    sql_text(
                        "ALTER TABLE test_plans ADD COLUMN "
                        "business_id VARCHAR(40) DEFAULT 'biz_default'"
                    )
                )
            connection.execute(
                sql_text(
                    "UPDATE test_plans SET business_id = 'biz_default' "
                    "WHERE business_id IS NULL OR business_id = ''"
                )
            )
            if not _column_exists(engine, "test_plans", "test_type"):
                connection.execute(
                    sql_text(
                        "ALTER TABLE test_plans ADD COLUMN "
                        "test_type VARCHAR(32) DEFAULT 'regression' NOT NULL"
                    )
                )
            connection.execute(
                sql_text(
                    "UPDATE test_plans SET test_type = 'regression' "
                    "WHERE test_type IS NULL OR test_type = ''"
                )
            )

    if _table_exists(engine, "plan_executions"):
        with engine.begin() as connection:
            if not _column_exists(engine, "plan_executions", "business_id"):
                connection.execute(
                    sql_text(
                        "ALTER TABLE plan_executions ADD COLUMN "
                        "business_id VARCHAR(40) DEFAULT 'biz_default'"
                    )
                )
            connection.execute(
                sql_text(
                    "UPDATE plan_executions SET business_id = 'biz_default' "
                    "WHERE business_id IS NULL OR business_id = ''"
                )
            )

    if _table_exists(engine, "discovered_pods"):
        pod_alterations = [
            ("pod_status_code", "ALTER TABLE discovered_pods ADD COLUMN pod_status_code INTEGER DEFAULT 1 NOT NULL"),
            ("stream_status", "ALTER TABLE discovered_pods ADD COLUMN stream_status INTEGER"),
            ("image_id", "ALTER TABLE discovered_pods ADD COLUMN image_id VARCHAR(255)"),
            ("image_name", "ALTER TABLE discovered_pods ADD COLUMN image_name VARCHAR(255)"),
            ("aosp_version", "ALTER TABLE discovered_pods ADD COLUMN aosp_version VARCHAR(32)"),
            ("display_layout_id", "ALTER TABLE discovered_pods ADD COLUMN display_layout_id VARCHAR(64)"),
            ("dc_id", "ALTER TABLE discovered_pods ADD COLUMN dc_id VARCHAR(64)"),
            ("dc_name", "ALTER TABLE discovered_pods ADD COLUMN dc_name VARCHAR(128)"),
            ("isp_code", "ALTER TABLE discovered_pods ADD COLUMN isp_code INTEGER"),
            ("region", "ALTER TABLE discovered_pods ADD COLUMN region VARCHAR(32)"),
            ("zone_id", "ALTER TABLE discovered_pods ADD COLUMN zone_id VARCHAR(64)"),
            ("config_code", "ALTER TABLE discovered_pods ADD COLUMN config_code VARCHAR(64)"),
            ("config_name", "ALTER TABLE discovered_pods ADD COLUMN config_name VARCHAR(64)"),
            ("config_type", "ALTER TABLE discovered_pods ADD COLUMN config_type INTEGER"),
            ("server_type_code", "ALTER TABLE discovered_pods ADD COLUMN server_type_code VARCHAR(64)"),
            ("intranet_ip", "ALTER TABLE discovered_pods ADD COLUMN intranet_ip VARCHAR(64)"),
            ("adb_address", "ALTER TABLE discovered_pods ADD COLUMN adb_address VARCHAR(128)"),
            ("adb_status", "ALTER TABLE discovered_pods ADD COLUMN adb_status INTEGER"),
            ("data_size", "ALTER TABLE discovered_pods ADD COLUMN data_size VARCHAR(32)"),
            ("data_size_used", "ALTER TABLE discovered_pods ADD COLUMN data_size_used VARCHAR(32)"),
            ("pod_created_at", "ALTER TABLE discovered_pods ADD COLUMN pod_created_at DATETIME"),
            ("node_id", "ALTER TABLE discovered_pods ADD COLUMN node_id INTEGER"),
            ("provider", "ALTER TABLE discovered_pods ADD COLUMN provider VARCHAR(64)"),
            ("project_name", "ALTER TABLE discovered_pods ADD COLUMN project_name VARCHAR(128)"),
            ("public_ip", "ALTER TABLE discovered_pods ADD COLUMN public_ip VARCHAR(64)"),
            ("os_type", "ALTER TABLE discovered_pods ADD COLUMN os_type VARCHAR(64)"),
            ("os_name", "ALTER TABLE discovered_pods ADD COLUMN os_name VARCHAR(255)"),
            ("instance_type", "ALTER TABLE discovered_pods ADD COLUMN instance_type VARCHAR(128)"),
            ("vcpu", "ALTER TABLE discovered_pods ADD COLUMN vcpu INTEGER"),
            ("memory_gib", "ALTER TABLE discovered_pods ADD COLUMN memory_gib INTEGER"),
            ("specification", "ALTER TABLE discovered_pods ADD COLUMN specification VARCHAR(255)"),
            ("agent_endpoint", "ALTER TABLE discovered_pods ADD COLUMN agent_endpoint VARCHAR(255)"),
            ("plugin_version", "ALTER TABLE discovered_pods ADD COLUMN plugin_version VARCHAR(64)"),
            ("script_version", "ALTER TABLE discovered_pods ADD COLUMN script_version VARCHAR(64)"),
            ("status_name", "ALTER TABLE discovered_pods ADD COLUMN status_name VARCHAR(64)"),
            ("status_message", "ALTER TABLE discovered_pods ADD COLUMN status_message VARCHAR(255)"),
            ("last_heartbeat_at", "ALTER TABLE discovered_pods ADD COLUMN last_heartbeat_at DATETIME"),
            ("node_updated_at", "ALTER TABLE discovered_pods ADD COLUMN node_updated_at DATETIME"),
        ]
        with engine.begin() as connection:
            for col_name, ddl in pod_alterations:
                if not _column_exists(engine, "discovered_pods", col_name):
                    connection.execute(sql_text(ddl))
            if _column_exists(engine, "discovered_pods", "online"):
                connection.execute(
                    sql_text(
                        "UPDATE discovered_pods "
                        "SET pod_status_code = CASE "
                        "WHEN online = 1 THEN 1 "
                        "WHEN remote_status = 'offline' THEN 2 "
                        "ELSE 2 END"
                    )
                )

    TestPlan.__table__.create(engine, checkfirst=True)
    TestPlanCase.__table__.create(engine, checkfirst=True)
    PlanExecution.__table__.create(engine, checkfirst=True)
    TagColorRegistry.__table__.create(engine, checkfirst=True)
    TestPlanSchedule.__table__.create(engine, checkfirst=True)
    ScheduleEvent.__table__.create(engine, checkfirst=True)
    _register_existing_case_tags(engine)


def data_directory_is_writable(path: Path) -> bool:
    probe_path: Path | None = None
    writable = False
    try:
        with NamedTemporaryFile(dir=path, delete=False) as probe:
            probe_path = Path(probe.name)
            probe.write(b"ready")
            probe.flush()
        writable = True
    except OSError:
        pass
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink()
            except OSError:
                writable = False
    return writable
