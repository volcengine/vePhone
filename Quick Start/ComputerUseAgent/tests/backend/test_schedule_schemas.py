from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cua_platform.test_plans.schemas import (
    CronPreviewResponse,
    ScheduleEventResponse,
    TestPlanScheduleCreate,
    TestPlanScheduleResponse,
    TestPlanScheduleUpdate,
)


def _make_config(**overrides):
    base = {
        "test_type": "regression",
        "device_strategy": "automatic",
        "pod_ids": [],
        "concurrency": 4,
    }
    base.update(overrides)
    return base


def test_create_schedule_valid():
    payload = TestPlanScheduleCreate(
        cron_expr="0 9 * * 1-5",
        timezone="Asia/Shanghai",
        execution_config=_make_config(),
    )
    assert payload.cron_expr == "0 9 * * 1-5"
    assert payload.enabled is True


def test_create_schedule_rejects_bad_cron():
    with pytest.raises(ValidationError):
        TestPlanScheduleCreate(
            cron_expr="bad",
            timezone="UTC",
            execution_config=_make_config(),
        )


def test_create_schedule_rejects_bad_timezone():
    with pytest.raises(ValidationError):
        TestPlanScheduleCreate(
            cron_expr="0 9 * * *",
            timezone="Not/Real",
            execution_config=_make_config(),
        )


def test_create_schedule_rejects_wrong_field_count():
    with pytest.raises(ValidationError):
        TestPlanScheduleCreate(
            cron_expr="0 9 * *",
            timezone="UTC",
            execution_config=_make_config(),
        )


def test_create_schedule_default_enabled():
    payload = TestPlanScheduleCreate(
        cron_expr="0 9 * * *",
        timezone="UTC",
        execution_config=_make_config(),
    )
    assert payload.enabled is True


def test_create_schedule_disabled():
    payload = TestPlanScheduleCreate(
        cron_expr="0 9 * * *",
        timezone="UTC",
        execution_config=_make_config(),
        enabled=False,
    )
    assert payload.enabled is False


def test_update_schedule_all_fields_optional():
    update = TestPlanScheduleUpdate()
    assert update.cron_expr is None
    assert update.timezone is None
    assert update.execution_config is None
    assert update.enabled is None


def test_update_schedule_partial():
    update = TestPlanScheduleUpdate(enabled=False)
    assert update.enabled is False
    assert update.cron_expr is None


def test_update_schedule_validates_cron():
    with pytest.raises(ValidationError):
        TestPlanScheduleUpdate(cron_expr="bad")


def test_schedule_response_from_attributes():
    now = datetime.now(timezone.utc)
    response = TestPlanScheduleResponse(
        id="schedule_1",
        test_plan_id="plan_1",
        cron_expr="0 9 * * *",
        timezone="UTC",
        enabled=True,
        next_run_at=now,
        last_run_at=None,
        last_skip_reason=None,
        execution_config={"device_strategy": "automatic"},
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    assert response.id == "schedule_1"
    assert response.cron_expr == "0 9 * * *"


def test_cron_preview_response():
    response = CronPreviewResponse(
        next_runs=[datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc)],
        human_description="每天 09:00",
    )
    assert len(response.next_runs) == 1
    assert response.human_description == "每天 09:00"


def test_schedule_event_response():
    now = datetime.now(timezone.utc)
    event = ScheduleEventResponse(
        id="event_1",
        schedule_id="schedule_1",
        event_type="triggered",
        trigger_type="scheduled",
        scheduled_for=now,
        fired_at=now,
        plan_execution_id="exec_1",
        skip_reason=None,
        error_message=None,
        created_at=now,
    )
    assert event.event_type == "triggered"
    assert event.plan_execution_id == "exec_1"
