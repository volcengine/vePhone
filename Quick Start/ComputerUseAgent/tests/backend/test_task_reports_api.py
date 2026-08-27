import csv
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from cua_platform.tasks.models import Task, TaskBatch
from cua_platform.tasks.state_machine import ExecutionStatus, Verdict
from cua_platform.test_plans.models import PlanExecution


def _create_case(client, title: str) -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "module": "报告",
            "content_markdown": f"## 执行任务\n- 验证 {title}",
            "tags": ["report"],
            "automation_level": "auto",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_plan(client, name: str, case_ids: list[str]) -> dict:
    response = client.post(
        "/api/v1/test-plans",
        json={
            "name": name,
            "description": "报告测试计划",
            "tags": ["回归"],
            "case_ids": case_ids,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_report(
    client,
    *,
    plan: dict | None = None,
    plan_name: str = "报告计划",
    task_states: list[
        tuple[ExecutionStatus, Verdict | None, str | None]
    ] | None = None,
    batch_status: ExecutionStatus = ExecutionStatus.RESULT_READY,
    batch_verdict: Verdict | None = Verdict.PASS,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    config_snapshot: dict | None = None,
) -> dict:
    states = task_states or [
        (ExecutionStatus.RESULT_READY, Verdict.PASS, None)
    ]
    case_ids = [
        _create_case(client, f"{plan_name}-用例-{index}-{uuid4().hex[:6]}")
        for index in range(len(states))
    ]
    resolved_plan = plan or _create_plan(
        client,
        f"{plan_name}-{uuid4().hex[:6]}",
        case_ids,
    )
    execution_id = f"execution_{uuid4().hex}"
    batch_id = f"batch_{uuid4().hex}"
    created = created_at or datetime(2026, 1, 1, 8, tzinfo=UTC)
    with client.app.state.session_factory() as db:
        batch = TaskBatch(
            id=batch_id,
            name=resolved_plan["name"],
            test_type="regression",
            selection_mode="test_plan",
            selection_snapshot={
                "test_plan_id": resolved_plan["id"],
                "case_ids": case_ids,
            },
            device_strategy="automatic",
            pod_ids=[],
            concurrency=1,
            device_wait_timeout_seconds=300,
            runner_type="mock",
            config_snapshot=config_snapshot or {"config_source": "global"},
            execution_status=batch_status,
            verdict=batch_verdict,
            idempotency_key=f"report-{uuid4().hex}",
            request_fingerprint="{}",
            created_by="admin",
            created_at=created,
            started_at=started_at,
            finished_at=finished_at,
        )
        for position, (case_id, state) in enumerate(
            zip(case_ids, states, strict=True)
        ):
            execution_status, verdict, failure_type = state
            task_started = (
                started_at
                if execution_status != ExecutionStatus.QUEUED
                else None
            )
            task_finished = (
                finished_at
                if execution_status
                in {ExecutionStatus.RESULT_READY, ExecutionStatus.CANCELLED}
                else None
            )
            batch.tasks.append(
                Task(
                    id=f"task_{uuid4().hex}",
                    case_id=case_id,
                    batch_position=position,
                    prompt_snapshot="run",
                    runner_type="mock",
                    scenario=f"报告用例 {position}",
                    created_by="admin",
                    execution_status=execution_status,
                    verdict=verdict,
                    failure_type=failure_type,
                    idempotency_key=f"task-{uuid4().hex}",
                    request_fingerprint="{}",
                    version=1,
                    created_at=created,
                    started_at=task_started,
                    finished_at=task_finished,
                )
            )
        db.add(batch)
        db.add(
            PlanExecution(
                id=execution_id,
                test_plan_id=resolved_plan["id"],
                task_batch_id=batch_id,
                plan_name_snapshot=resolved_plan["name"],
                plan_tags_snapshot=["回归"],
                case_ids_snapshot=case_ids,
                device_strategy_snapshot="automatic",
                pod_ids_snapshot=[],
                concurrency_snapshot=1,
                runner_type_snapshot="mock",
                config_snapshot=config_snapshot
                or {"config_source": "global"},
                created_by="admin",
                created_at=created,
            )
        )
        db.commit()
    return {
        "execution_id": execution_id,
        "batch_id": batch_id,
        "plan": resolved_plan,
        "case_ids": case_ids,
    }


@pytest.mark.parametrize(
    ("batch_status", "batch_verdict", "failure_type", "expected"),
    [
        (ExecutionStatus.QUEUED, None, None, "queued"),
        (ExecutionStatus.RUNNING, None, None, "running"),
        (ExecutionStatus.RESULT_READY, Verdict.PASS, None, "success"),
        (
            ExecutionStatus.RESULT_READY,
            Verdict.FAIL,
            "assertion_failed",
            "failure",
        ),
        (
            ExecutionStatus.RESULT_READY,
            Verdict.FAIL,
            "device_unavailable",
            "exception",
        ),
        (
            ExecutionStatus.RESULT_READY,
            Verdict.FAIL,
            "evidence_missing",
            "exception",
        ),
        (
            ExecutionStatus.RESULT_READY,
            Verdict.FAIL,
            "unknown_failure",
            "exception",
        ),
        (ExecutionStatus.CANCELLED, None, None, "cancelled"),
    ],
)
def test_report_status_mapping(
    authenticated_client,
    batch_status,
    batch_verdict,
    failure_type,
    expected,
):
    task_status = batch_status
    task_verdict = batch_verdict
    report = _seed_report(
        authenticated_client,
        batch_status=batch_status,
        batch_verdict=batch_verdict,
        task_states=[(task_status, task_verdict, failure_type)],
    )

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert response.status_code == 200, response.text
    assert response.json()["report_status"] == expected


def test_report_status_running_when_some_children_finished_and_others_queued(
    authenticated_client,
):
    report = _seed_report(
        authenticated_client,
        batch_status=ExecutionStatus.QUEUED,
        batch_verdict=None,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (ExecutionStatus.QUEUED, None, None),
        ],
    )

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_status"] == "running"
    assert body["queued_count"] == 1
    assert body["running_count"] == 0


def test_report_uses_snapshot_pass_rate_duration_and_public_config(
    authenticated_client,
    monkeypatch,
):
    now = datetime(2026, 1, 1, 9, 2, tzinfo=UTC)
    monkeypatch.setattr(
        "cua_platform.test_plans.reports.utc_now",
        lambda: now,
    )
    report = _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "assertion_failed",
            ),
            (ExecutionStatus.RUNNING, None, None),
        ],
        batch_status=ExecutionStatus.RUNNING,
        batch_verdict=None,
        started_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
        config_snapshot={
            "config_source": "custom",
            "callback_info": {
                "url": "https://callback.example.com",
                "authorization": "Bearer secret",
            },
        },
    )

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pass_rate"] == 50.0
    assert body["duration_seconds"] == 120
    assert body["pass_count"] == 2
    assert body["fail_count"] == 1
    assert body["running_count"] == 1
    assert body["config_snapshot"]["callback_info"]["authorization"] == "***"
    assert "Bearer secret" not in response.text


def test_report_duration_is_null_before_start_and_terminal_uses_finish(
    authenticated_client,
):
    queued = _seed_report(
        authenticated_client,
        batch_status=ExecutionStatus.QUEUED,
        batch_verdict=None,
        task_states=[(ExecutionStatus.QUEUED, None, None)],
    )
    terminal = _seed_report(
        authenticated_client,
        batch_status=ExecutionStatus.RESULT_READY,
        batch_verdict=Verdict.PASS,
        started_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 10, 1, 5, tzinfo=UTC),
    )

    queued_body = authenticated_client.get(
        f"/api/v1/task-reports/{queued['execution_id']}"
    ).json()
    terminal_body = authenticated_client.get(
        f"/api/v1/task-reports/{terminal['execution_id']}"
    ).json()

    assert queued_body["duration_seconds"] is None
    assert terminal_body["duration_seconds"] == 65


def test_report_timing_uses_child_task_bounds_when_batch_started_late(
    authenticated_client,
    monkeypatch,
):
    now = datetime(2026, 1, 1, 10, tzinfo=UTC)
    monkeypatch.setattr(
        "cua_platform.test_plans.reports.utc_now",
        lambda: now,
    )
    first_task_started = datetime(2026, 1, 1, 9, tzinfo=UTC)
    late_batch_started = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)
    report = _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (ExecutionStatus.RUNNING, None, None),
        ],
        batch_status=ExecutionStatus.RUNNING,
        batch_verdict=None,
        started_at=late_batch_started,
    )
    with authenticated_client.app.state.session_factory() as db:
        tasks = list(
            db.query(Task)
            .filter(Task.batch_id == report["batch_id"])
            .order_by(Task.batch_position)
        )
        tasks[0].started_at = first_task_started
        tasks[0].finished_at = first_task_started + timedelta(minutes=5)
        tasks[1].started_at = first_task_started + timedelta(minutes=10)
        db.commit()

    detail = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )
    listed = authenticated_client.get(
        f"/api/v1/test-plans/{report['plan']['id']}/executions",
        params={"page": 1, "page_size": 10},
    )

    assert detail.status_code == 200, detail.text
    assert detail.json()["started_at"] == "2026-01-01T09:00:00Z"
    assert detail.json()["duration_seconds"] == 3600
    assert listed.status_code == 200, listed.text
    listed_item = listed.json()["items"][0]
    assert listed_item["started_at"] == "2026-01-01T09:00:00Z"
    assert listed_item["duration_seconds"] == 3600


def test_report_list_stats_filters_and_page_sizes_match(
    authenticated_client,
):
    plan_case = _create_case(authenticated_client, "筛选计划用例")
    plan = _create_plan(
        authenticated_client,
        f"筛选计划-{uuid4().hex[:6]}",
        [plan_case],
    )
    after = datetime(2026, 2, 1, tzinfo=UTC)
    success = _seed_report(
        authenticated_client,
        plan=plan,
        created_at=after + timedelta(hours=1),
        batch_status=ExecutionStatus.RESULT_READY,
        batch_verdict=Verdict.PASS,
    )
    _seed_report(
        authenticated_client,
        plan=plan,
        created_at=after + timedelta(hours=2),
        batch_status=ExecutionStatus.RESULT_READY,
        batch_verdict=Verdict.FAIL,
        task_states=[
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "assertion_failed",
            )
        ],
    )
    _seed_report(
        authenticated_client,
        created_at=after - timedelta(days=1),
    )

    params = {
        "test_plan_id": plan["id"],
        "status": "success",
        "created_after": after.isoformat(),
        "page": 1,
        "page_size": 10,
    }
    listed = authenticated_client.get("/api/v1/task-reports", params=params)
    stats = authenticated_client.get(
        "/api/v1/task-reports/stats",
        params={key: value for key, value in params.items() if key not in {"page", "page_size"}},
    )

    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["execution_id"] == success["execution_id"]
    assert stats.status_code == 200, stats.text
    assert stats.json() == {
        "report_count": 1,
        "success_count": 1,
        "failure_count": 0,
        "average_pass_rate": 100.0,
    }


def test_report_list_filters_by_task_batch_id_search(authenticated_client):
    matched = _seed_report(authenticated_client, plan_name="搜索命中")
    _seed_report(authenticated_client, plan_name="搜索未命中")

    response = authenticated_client.get(
        "/api/v1/task-reports",
        params={
            "search": matched["batch_id"][6:18],
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["task_batch_id"] == matched["batch_id"]
    for page_size in (10, 20, 50):
        response = authenticated_client.get(
            "/api/v1/task-reports",
            params={"page_size": page_size},
        )
        assert response.status_code == 200
    assert authenticated_client.get(
        "/api/v1/task-reports",
        params={"page_size": 11},
    ).status_code == 422


def test_report_stats_average_uses_snapshot_denominator(
    authenticated_client,
):
    _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "assertion_failed",
            ),
        ],
        batch_verdict=Verdict.FAIL,
    )
    _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
        ],
    )

    response = authenticated_client.get("/api/v1/task-reports/stats")

    assert response.status_code == 200
    assert response.json()["report_count"] == 2
    assert response.json()["success_count"] == 1
    assert response.json()["failure_count"] == 1
    assert response.json()["average_pass_rate"] == 75.0


def test_report_stats_failure_count_excludes_exception(
    authenticated_client,
):
    _seed_report(
        authenticated_client,
        batch_verdict=Verdict.FAIL,
        task_states=[
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "assertion_failed",
            )
        ],
    )
    exception = _seed_report(
        authenticated_client,
        batch_verdict=Verdict.FAIL,
        task_states=[
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "runner_interrupted",
            )
        ],
    )

    all_stats = authenticated_client.get("/api/v1/task-reports/stats")
    exception_stats = authenticated_client.get(
        "/api/v1/task-reports/stats",
        params={"status": "exception"},
    )
    exception_list = authenticated_client.get(
        "/api/v1/task-reports",
        params={"status": "exception"},
    )

    assert all_stats.status_code == 200
    assert all_stats.json()["report_count"] == 2
    assert all_stats.json()["failure_count"] == 1
    assert exception_stats.status_code == 200
    assert exception_stats.json()["report_count"] == 1
    assert exception_stats.json()["failure_count"] == 0
    assert exception_list.status_code == 200
    assert [
        item["execution_id"] for item in exception_list.json()["items"]
    ] == [exception["execution_id"]]


def test_report_list_and_detail_map_raw_unknown_enums(
    authenticated_client,
):
    report = _seed_report(authenticated_client)
    with authenticated_client.app.state.session_factory() as db:
        db.execute(
            text(
                "UPDATE task_batches "
                "SET execution_status = 'illegal_batch_status', "
                "verdict = 'illegal_batch_verdict' "
                "WHERE id = :batch_id"
            ),
            {"batch_id": report["batch_id"]},
        )
        db.execute(
            text(
                "UPDATE tasks "
                "SET execution_status = 'illegal_task_status', "
                "verdict = 'illegal_task_verdict' "
                "WHERE batch_id = :batch_id"
            ),
            {"batch_id": report["batch_id"]},
        )
        db.commit()

    listed = authenticated_client.get("/api/v1/task-reports")
    detail = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert listed.status_code == 200
    listed_report = next(
        item
        for item in listed.json()["items"]
        if item["execution_id"] == report["execution_id"]
    )
    assert listed_report["report_status"] == "exception"
    assert detail.status_code == 200
    assert detail.json()["report_status"] == "exception"
    assert detail.json()["tasks"][0]["execution_status"] == "unknown"
    assert detail.json()["tasks"][0]["verdict"] == "unknown"


def test_deleted_plan_report_remains_readable_from_snapshot(
    authenticated_client,
):
    report = _seed_report(authenticated_client, plan_name="历史计划")
    deleted = authenticated_client.delete(
        f"/api/v1/test-plans/{report['plan']['id']}"
    )

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert deleted.status_code == 204
    assert response.status_code == 200
    assert response.json()["plan_name_snapshot"].startswith("历史计划")


def test_report_detail_marks_soft_deleted_cases(authenticated_client):
    report = _seed_report(authenticated_client, plan_name="软删除用例报告")
    case_id = report["case_ids"][0]
    authenticated_client.delete(f"/api/v1/test-plans/{report['plan']['id']}")
    deleted = authenticated_client.delete(f"/api/v1/cases/{case_id}")

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert deleted.status_code == 204
    assert response.status_code == 200
    task = response.json()["tasks"][0]
    assert task["case_id"] == case_id
    assert task["case_deleted"] is True


def test_report_detail_exposes_task_runtime_metrics(authenticated_client):
    report = _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
        ],
    )
    with authenticated_client.app.state.session_factory() as db:
        tasks = list(
            db.query(Task)
            .filter(Task.batch_id == report["batch_id"])
            .order_by(Task.batch_position)
        )
        tasks[0].result_assets = {
            "usage": {"in_tokens": 1234, "out_tokens": "56"},
            "total_steps": 7,
            "duration_ms": 125000,
        }
        tasks[0].remote_run_id = "run_report_detail"
        tasks[1].result_assets = {
            "usage": {"in_tokens": "bad", "out_tokens": None},
            "total_steps": "bad",
        }
        db.commit()

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}"
    )

    assert response.status_code == 200, response.text
    first, second = response.json()["tasks"]
    assert first["input_tokens"] == 1234
    assert first["output_tokens"] == 56
    assert first["total_steps"] == 7
    assert first["duration_seconds"] == 125
    assert first["remote_run_id"] == "run_report_detail"
    assert second["input_tokens"] is None
    assert second["output_tokens"] is None
    assert second["total_steps"] is None
    assert second["remote_run_id"] is None


def test_report_download_markdown_contains_kpis_snapshot_and_tasks(
    authenticated_client,
):
    report = _seed_report(
        authenticated_client,
        plan_name="下载报告",
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "assertion_failed",
            ),
        ],
        batch_verdict=Verdict.FAIL,
        started_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 10, 2, 5, tzinfo=UTC),
    )
    with authenticated_client.app.state.session_factory() as db:
        task = (
            db.query(Task)
            .filter(Task.batch_id == report["batch_id"])
            .order_by(Task.batch_position)
            .first()
        )
        task.result_assets = {
            "usage": {"in_tokens": 1234, "out_tokens": 56},
            "total_steps": 7,
        }
        task.remote_run_id = "run_download_md"
        db.commit()

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}/download",
        params={"format": "markdown"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/markdown")
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="cua-test-report-{report["batch_id"]}.md"'
    )
    body = response.text
    assert "# 测试报告：下载报告" in body
    assert "执行结果：失败" in body
    assert "测试通过率：50%" in body
    assert "总执行时长：2 分 5 秒" in body
    assert "## 执行快照" in body
    assert "设备策略：自动分配" in body
    assert "并发数：1" in body
    assert "## 子任务结果" in body
    assert "Run ID" in body
    assert "run_download_md" in body
    assert "输入 Token" in body
    assert "输出 Token" in body
    assert "执行步数" in body
    assert "1234" in body
    assert "56" in body
    assert "7" in body
    assert "assertion_failed" in body
    assert report["case_ids"][0] in body


def test_report_download_csv_groups_kpis_snapshot_and_subtask_rows(
    authenticated_client,
):
    report = _seed_report(
        authenticated_client,
        plan_name="CSV报告",
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None),
            (
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "runner_interrupted",
            ),
        ],
        batch_verdict=Verdict.FAIL,
        started_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 10, 2, 5, tzinfo=UTC),
    )
    with authenticated_client.app.state.session_factory() as db:
        tasks = list(
            db.query(Task)
            .filter(Task.batch_id == report["batch_id"])
            .order_by(Task.batch_position)
        )
        tasks[1].result_assets = {
            "usage": {"in_tokens": 987, "out_tokens": 65},
            "total_steps": 4,
        }
        tasks[1].remote_run_id = "run_download_csv"
        db.commit()

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}/download",
        params={"format": "csv"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="cua-test-report-{report["batch_id"]}.csv"'
    )
    rows = list(csv.reader(StringIO(response.text)))
    assert rows[:3] == [
        ["KPI 值"],
        ["报告ID", report["execution_id"]],
        ["任务批次ID", report["batch_id"]],
    ]
    assert rows[3][0] == "测试计划"
    assert rows[3][1].startswith("CSV报告")
    assert rows[4:10] == [
        ["执行结果", "异常"],
        ["测试通过率", "50%"],
        ["通过子任务", "1"],
        ["总子任务", "2"],
        ["总执行时长", "2 分 5 秒"],
        [],
    ]
    assert ["执行快照"] in rows
    assert ["设备策略", "自动分配"] in rows
    assert ["并发数", "1"] in rows
    assert ["子任务结果"] in rows
    assert [
        "任务ID",
        "Run ID",
        "用例ID",
        "用例标题",
        "任务状态",
        "任务结果",
        "失败类型",
        "任务创建时间",
        "任务执行时长",
        "输入 Token",
        "输出 Token",
        "执行步数",
    ] in rows
    assert any(
        row[1] == "run_download_csv"
        and row[6] == "runner_interrupted"
        and row[8] == "2 分 5 秒"
        and row[9:12] == ["987", "65", "4"]
        for row in rows
        if len(row) == 12
    )


def test_report_download_rejects_non_downloadable_status(authenticated_client):
    report = _seed_report(
        authenticated_client,
        batch_status=ExecutionStatus.RUNNING,
        batch_verdict=None,
        task_states=[(ExecutionStatus.RUNNING, None, None)],
    )

    response = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}/download",
        params={"format": "markdown"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_report_download_unavailable"


def test_report_detail_paginates_tasks_in_plan_order(
    authenticated_client,
):
    report = _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None)
            for _index in range(11)
        ],
    )

    first = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}",
        params={"page": 1, "page_size": 10},
    )
    second = authenticated_client.get(
        f"/api/v1/task-reports/{report['execution_id']}",
        params={"page": 2, "page_size": 10},
    )

    assert first.status_code == 200
    assert first.json()["tasks_total"] == 11
    assert len(first.json()["tasks"]) == 10
    assert [item["case_id"] for item in first.json()["tasks"]] == (
        report["case_ids"][:10]
    )
    assert len(second.json()["tasks"]) == 1
    task = second.json()["tasks"][0]
    assert task["case_id"] == report["case_ids"][10]
    assert set(task) >= {
        "task_id",
        "case_id",
        "case_title",
        "execution_status",
        "verdict",
        "failure_type",
        "created_at",
        "started_at",
        "finished_at",
        "duration_seconds",
    }


def test_plan_execution_history_is_bounded_and_unknowns_return_404(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "历史计划用例")
    plan = _create_plan(
        authenticated_client,
        f"历史计划-{uuid4().hex[:6]}",
        [case_id],
    )
    execution_ids = [
        _seed_report(
            authenticated_client,
            plan=plan,
            created_at=datetime(2026, 3, 1, tzinfo=UTC)
            + timedelta(minutes=index),
        )["execution_id"]
        for index in range(12)
    ]

    response = authenticated_client.get(
        f"/api/v1/test-plans/{plan['id']}/executions",
        params={"page": 1, "page_size": 10},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 12
    assert len(response.json()["items"]) == 10
    assert response.json()["items"][0]["execution_id"] == execution_ids[-1]
    assert authenticated_client.get(
        "/api/v1/test-plans/plan_missing/executions"
    ).status_code == 404
    assert authenticated_client.get(
        "/api/v1/task-reports/execution_missing"
    ).status_code == 404


def test_report_list_query_count_does_not_grow_with_page_size(
    authenticated_client,
):
    for index in range(12):
        _seed_report(
            authenticated_client,
            created_at=datetime(2026, 4, 1, tzinfo=UTC)
            + timedelta(minutes=index),
        )
    statements: list[str] = []

    def capture(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        statements.append(statement)

    event.listen(
        authenticated_client.app.state.engine,
        "before_cursor_execute",
        capture,
    )
    try:
        single = authenticated_client.get(
            "/api/v1/task-reports",
            params={"page_size": 10, "page": 1},
        )
        single_count = len(statements)
        statements.clear()
        multiple = authenticated_client.get(
            "/api/v1/task-reports",
            params={"page_size": 50, "page": 1},
        )
        multiple_count = len(statements)
    finally:
        event.remove(
            authenticated_client.app.state.engine,
            "before_cursor_execute",
            capture,
        )

    assert single.status_code == 200
    assert multiple.status_code == 200
    assert len(single.json()["items"]) == 10
    assert len(multiple.json()["items"]) == 12
    assert multiple_count == single_count


def test_report_detail_query_count_does_not_grow_with_task_page_size(
    authenticated_client,
):
    report = _seed_report(
        authenticated_client,
        task_states=[
            (ExecutionStatus.RESULT_READY, Verdict.PASS, None)
            for _index in range(11)
        ],
    )
    statements: list[str] = []

    def capture(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        statements.append(statement)

    event.listen(
        authenticated_client.app.state.engine,
        "before_cursor_execute",
        capture,
    )
    try:
        first = authenticated_client.get(
            f"/api/v1/task-reports/{report['execution_id']}",
            params={"page_size": 10},
        )
        first_count = len(statements)
        statements.clear()
        all_tasks = authenticated_client.get(
            f"/api/v1/task-reports/{report['execution_id']}",
            params={"page_size": 20},
        )
        all_count = len(statements)
    finally:
        event.remove(
            authenticated_client.app.state.engine,
            "before_cursor_execute",
            capture,
        )

    assert first.status_code == 200
    assert all_tasks.status_code == 200
    assert len(first.json()["tasks"]) == 10
    assert len(all_tasks.json()["tasks"]) == 11
    assert all_count == first_count
