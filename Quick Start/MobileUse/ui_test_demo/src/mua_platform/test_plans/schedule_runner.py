from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from mua_platform.settings.repository import SettingRepository
from mua_platform.settings.service import SettingsService
from mua_platform.test_plans.executions import (
    PlanExecutionCreate,
    PlanExecutionService,
)
from mua_platform.test_plans.schedule_service import ScheduleService
from mua_platform.test_plans.service import TestPlanService

logger = logging.getLogger("mua_platform.schedule_runner")


class ScheduleTrigger:
    def __init__(
        self,
        db: Session,
        settings: Any,
        setting_cipher: Any,
    ):
        self.db = db
        self.settings = settings
        self.setting_cipher = setting_cipher

    def trigger_due(
        self,
        now: datetime,
        *,
        trigger_type: str = "scheduled",
    ) -> list[str]:
        schedule_service = ScheduleService(self.db)
        due_schedules = schedule_service.claim_due(now)
        created_execution_ids: list[str] = []

        for schedule in due_schedules:
            expected_next = schedule.next_run_at
            from mua_platform.test_plans.scheduling import compute_next_run

            next_run = compute_next_run(
                schedule.cron_expr, schedule.timezone, now
            )
            result = self.db.execute(
                text(
                    "UPDATE test_plan_schedules "
                    "SET next_run_at = :next_run, last_run_at = :now "
                    "WHERE id = :id AND next_run_at = :expected "
                    "AND enabled = 1"
                ),
                {
                    "next_run": next_run,
                    "now": now,
                    "id": schedule.id,
                    "expected": expected_next,
                },
            )
            self.db.commit()
            if result.rowcount == 0:
                continue

            self.db.refresh(schedule)
            scheduled_for = expected_next

            test_plan_service = TestPlanService(self.db)
            if test_plan_service._has_active_execution(
                schedule.test_plan_id
            ):
                schedule_service.record_event(
                    schedule,
                    event_type="skipped",
                    trigger_type=trigger_type,
                    scheduled_for=scheduled_for,
                    fired_at=now,
                    skip_reason="active_execution",
                )
                continue

            try:
                execution_id = self._create_execution(schedule, now)
                schedule_service.record_event(
                    schedule,
                    event_type="triggered",
                    trigger_type=trigger_type,
                    scheduled_for=scheduled_for,
                    fired_at=now,
                    plan_execution_id=execution_id,
                )
                created_execution_ids.append(execution_id)
            except Exception as exc:
                logger.exception(
                    "schedule_trigger_failed",
                    extra={"schedule_id": schedule.id},
                )
                schedule_service.record_event(
                    schedule,
                    event_type="failed",
                    trigger_type=trigger_type,
                    scheduled_for=scheduled_for,
                    fired_at=now,
                    error_message=str(exc)[:500],
                )

        return created_execution_ids

    def run_once(
        self,
        schedule,
        *,
        trigger_type: str = "manual",
    ) -> str | None:
        now = datetime.now(UTC)
        schedule_service = ScheduleService(self.db)
        test_plan_service = TestPlanService(self.db)

        if test_plan_service._has_active_execution(
            schedule.test_plan_id
        ):
            schedule_service.record_event(
                schedule,
                event_type="skipped",
                trigger_type=trigger_type,
                scheduled_for=now,
                fired_at=now,
                skip_reason="active_execution",
            )
            return None

        try:
            execution_id = self._create_execution(schedule, now)
            schedule_service.record_event(
                schedule,
                event_type="triggered",
                trigger_type=trigger_type,
                scheduled_for=now,
                fired_at=now,
                plan_execution_id=execution_id,
            )
            return execution_id
        except Exception as exc:
            logger.exception(
                "schedule_manual_run_failed",
                extra={"schedule_id": schedule.id},
            )
            schedule_service.record_event(
                schedule,
                event_type="failed",
                trigger_type=trigger_type,
                scheduled_for=now,
                fired_at=now,
                error_message=str(exc)[:500],
            )
            return None

    def _create_execution(self, schedule, now: datetime) -> str:
        runner_config = SettingsService(
            SettingRepository(
                self.db,
                self.setting_cipher,
                self.settings.runner_setting_defaults(),
            )
        ).get_runner_config(schedule.business_id)

        config = dict(schedule.execution_config)
        payload = PlanExecutionCreate(
            test_type=config.get("test_type", "regression"),
            device_strategy=config.get("device_strategy", "automatic"),
            pod_ids=config.get("pod_ids", []),
            concurrency=config.get("concurrency", 1),
            device_wait_timeout_seconds=config.get(
                "device_wait_timeout_seconds"
            ),
            timeout_seconds=config.get("timeout_seconds"),
            agent_config_mode=config.get("agent_config_mode", "global"),
            agent_options=config.get("agent_options"),
            idempotency_key=f"schedule:{schedule.id}:{now.isoformat()}",
        )

        snapshot = runner_config.execution_snapshot()
        snapshot["business_id"] = schedule.business_id

        result = PlanExecutionService(self.db).create(
            schedule.test_plan_id,
            payload,
            created_by=f"schedule:{schedule.created_by}",
            runner_type=runner_config.mode,
            config_snapshot=snapshot,
            device_wait_timeout_seconds=(
                payload.device_wait_timeout_seconds
                or self.settings.device_wait_timeout_seconds
            ),
            business_id=schedule.business_id,
        )
        return result.execution.id
