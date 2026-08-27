from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cua_platform.cases.models import TestCase
from cua_platform.db import Base
from cua_platform.test_plans.models import TestPlan, TestPlanCase
from cua_platform.test_plans.schedule_service import (
    ScheduleAlreadyExistsError,
    ScheduleNotFoundError,
    ScheduleService,
)
from cua_platform.test_plans.schemas import TestPlanScheduleCreate


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def plan(db):
    case = TestCase(
        id=f"case_{uuid4().hex}",
        title="schedule test case",
        created_by="admin",
        content_markdown="## 步骤\n- 测试",
    )
    db.add(case)
    plan = TestPlan(
        id=f"plan_{uuid4().hex}",
        name="Schedule Test Plan",
        name_key="schedule-test-plan",
        test_type="regression",
        tags=[],
        created_by="admin",
    )
    plan.cases = [TestPlanCase(case_id=case.id, position=0)]
    db.add(plan)
    db.commit()
    return plan


def _make_schedule(cron="0 9 * * *", tz="UTC", **overrides):
    payload = {
        "cron_expr": cron,
        "timezone": tz,
        "execution_config": {
            "test_type": "regression",
            "device_strategy": "automatic",
            "pod_ids": [],
            "concurrency": 1,
        },
        "enabled": True,
    }
    payload.update(overrides)
    return TestPlanScheduleCreate(**payload)


def test_create_schedule(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    assert schedule.test_plan_id == plan.id
    assert schedule.cron_expr == "0 9 * * *"
    assert schedule.enabled is True
    assert schedule.next_run_at is not None
    assert schedule.execution_config["concurrency"] == 1


def test_create_schedule_duplicate_rejected(db, plan):
    service = ScheduleService(db)
    service.create(plan.id, _make_schedule(), created_by="admin")
    with pytest.raises(ScheduleAlreadyExistsError):
        service.create(plan.id, _make_schedule(cron="0 10 * * *"), created_by="admin")


def test_create_schedule_plan_not_found(db):
    service = ScheduleService(db)
    with pytest.raises(ScheduleNotFoundError):
        service.create("nonexistent", _make_schedule(), created_by="admin")


def test_get_schedule(db, plan):
    service = ScheduleService(db)
    created = service.create(plan.id, _make_schedule(), created_by="admin")
    fetched = service.get(plan.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_get_schedule_returns_none_when_missing(db):
    service = ScheduleService(db)
    assert service.get("nonexistent") is None


def test_update_schedule_cron_recalculates_next_run(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(cron="0 9 * * *"), created_by="admin")
    original_next = schedule.next_run_at
    updated = service.update(plan.id, _make_schedule(cron="0 10 * * *"))
    assert updated.cron_expr == "0 10 * * *"
    assert updated.next_run_at != original_next


def test_update_schedule_enabled_does_not_recalculate(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    original_next = schedule.next_run_at
    updated = service.update(plan.id, enabled=False)
    assert updated.enabled is False
    assert updated.next_run_at == original_next


def test_update_schedule_not_found(db):
    service = ScheduleService(db)
    with pytest.raises(ScheduleNotFoundError):
        service.update("nonexistent", enabled=False)


def test_set_enabled_true_recalculates_when_re_enabled(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    service.update(plan.id, enabled=False)
    # Use a time far in the future so next_run definitely changes
    future_now = datetime.now(UTC) + timedelta(hours=2)
    updated = service.set_enabled(plan.id, True, now=future_now)
    assert updated.enabled is True
    # next_run should be after the future_now
    assert updated.next_run_at.replace(tzinfo=UTC) >= future_now


def test_delete_schedule(db, plan):
    service = ScheduleService(db)
    service.create(plan.id, _make_schedule(), created_by="admin")
    assert service.delete(plan.id) is True
    assert service.get(plan.id) is None


def test_delete_schedule_not_found(db):
    service = ScheduleService(db)
    assert service.delete("nonexistent") is False


def test_claim_due_returns_due_schedules(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(cron="*/1 * * * *"), created_by="admin")
    schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=5)
    db.commit()
    due = service.claim_due(datetime.now(UTC))
    assert any(s.id == schedule.id for s in due)


def test_claim_due_excludes_disabled(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=5)
    schedule.enabled = False
    db.commit()
    due = service.claim_due(datetime.now(UTC))
    assert all(s.id != schedule.id for s in due)


def test_claim_due_excludes_future(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(cron="0 9 31 12 *"), created_by="admin")
    due = service.claim_due(datetime.now(UTC))
    assert all(s.id != schedule.id for s in due)


def test_advance_next_run_updates_timestamp(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(cron="0 * * * *"), created_by="admin")
    old_next = schedule.next_run_at
    later = datetime.now(UTC) + timedelta(hours=2)
    updated = service.advance_next_run(schedule, later)
    assert updated.last_run_at.replace(tzinfo=UTC) == later
    assert updated.next_run_at.replace(tzinfo=UTC) >= old_next.replace(tzinfo=UTC)


def test_record_event_persists(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    now = datetime.now(UTC)
    event = service.record_event(
        schedule,
        event_type="skipped",
        trigger_type="scheduled",
        scheduled_for=now,
        fired_at=now,
        skip_reason="active_execution",
    )
    assert event.id is not None
    events, total = service.list_events(plan.id, page=1, page_size=10)
    assert total == 1
    assert events[0].event_type == "skipped"
    assert events[0].skip_reason == "active_execution"


def test_record_event_triggered_with_execution_id(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    now = datetime.now(UTC)
    service.record_event(
        schedule,
        event_type="triggered",
        trigger_type="scheduled",
        scheduled_for=now,
        fired_at=now,
        plan_execution_id="exec_123",
    )
    events, _ = service.list_events(plan.id, page=1, page_size=10)
    assert events[0].plan_execution_id == "exec_123"


def test_list_events_pagination(db, plan):
    service = ScheduleService(db)
    schedule = service.create(plan.id, _make_schedule(), created_by="admin")
    now = datetime.now(UTC)
    for i in range(5):
        service.record_event(
            schedule,
            event_type="triggered",
            trigger_type="scheduled",
            scheduled_for=now - timedelta(minutes=i),
            fired_at=now - timedelta(minutes=i),
        )
    events, total = service.list_events(plan.id, page=1, page_size=2)
    assert total == 5
    assert len(events) == 2


def test_list_events_empty_for_missing_schedule(db):
    service = ScheduleService(db)
    events, total = service.list_events("nonexistent")
    assert total == 0
    assert events == []


def test_update_schedule_execution_config(db, plan):
    service = ScheduleService(db)
    service.create(plan.id, _make_schedule(), created_by="admin")
    updated = service.update(
        plan.id,
        _make_schedule(execution_config={
            "test_type": "regression",
            "device_strategy": "automatic",
            "pod_ids": [],
            "concurrency": 8,
        }),
    )
    assert updated.execution_config["concurrency"] == 8
