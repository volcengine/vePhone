from __future__ import annotations

import csv
from io import StringIO
from datetime import UTC, datetime

from sqlalchemy import Select, String, case, cast, func, select
from sqlalchemy.orm import Session

from cua_platform.business.models import DEFAULT_BUSINESS_ID
from cua_platform.cases.models import TestCase
from cua_platform.tasks.execution_config import public_execution_config
from cua_platform.tasks.models import Task, TaskBatch
from cua_platform.tasks.schemas import TaskExecutionConfig
from cua_platform.tasks.state_machine import ExecutionStatus, Verdict
from cua_platform.test_plans.models import PlanExecution
from cua_platform.test_plans.schemas import (
    PlanReportDetail,
    PlanReportStats,
    PlanReportSummary,
    PlanReportTask,
    ReportStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def report_status(
    batch_status: str,
    batch_verdict: str | None,
    failure_types: set[str],
    *,
    pass_count: int = 0,
    fail_count: int = 0,
    exception_count: int = 0,
    cancelled_count: int = 0,
    queued_count: int = 0,
    running_count: int = 0,
    total_count: int = 0,
) -> ReportStatus:
    effective = effective_report_status(
        batch_status,
        batch_verdict,
        pass_count=pass_count,
        fail_count=fail_count,
        exception_count=exception_count,
        cancelled_count=cancelled_count,
        queued_count=queued_count,
        running_count=running_count,
        total_count=total_count,
    )
    if effective is not None:
        return effective
    if batch_status == ExecutionStatus.QUEUED.value:
        return "queued"
    if batch_status == ExecutionStatus.RUNNING.value:
        return "running"
    if batch_status == ExecutionStatus.CANCELLED.value:
        return "cancelled"
    if (
        batch_status == ExecutionStatus.RESULT_READY.value
        and batch_verdict == Verdict.PASS.value
    ):
        return "success"
    if failure_types - {"assertion_failed"}:
        return "exception"
    if (
        batch_status == ExecutionStatus.RESULT_READY.value
        and batch_verdict == Verdict.FAIL.value
    ):
        return "failure"
    return "exception"


def effective_report_status(
    batch_status: str,
    batch_verdict: str | None,
    *,
    pass_count: int,
    fail_count: int,
    exception_count: int,
    cancelled_count: int,
    queued_count: int,
    running_count: int,
    total_count: int,
) -> ReportStatus | None:
    terminal_count = pass_count + fail_count + exception_count + cancelled_count
    if running_count > 0 or (queued_count > 0 and terminal_count > 0):
        return "running"
    if total_count > 0 and queued_count == total_count:
        return "queued"
    if total_count > 0 and terminal_count == total_count:
        if cancelled_count == total_count:
            return "cancelled"
        if exception_count > 0:
            return "exception"
        if fail_count > 0:
            return "failure"
        if batch_verdict == Verdict.PASS.value or pass_count == total_count:
            return "success"
        return "exception"
    if batch_status == ExecutionStatus.RUNNING.value:
        return "running"
    return None


def pass_rate(pass_count: int, snapshot_total: int) -> float:
    if not snapshot_total:
        return 0.0
    return round(pass_count / snapshot_total * 100, 2)


class PlanReportService:
    def __init__(self, db: Session):
        self.db = db

    def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        test_plan_id: str | None,
        status: ReportStatus | None,
        created_after: datetime | None,
        search: str | None = None,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> tuple[list[PlanReportSummary], int]:
        aggregate = _task_aggregate()
        status_column = _report_status_expression(aggregate).label(
            "report_status"
        )
        filters = _filters(
            status_column=status_column,
            test_plan_id=test_plan_id,
            status=status,
            created_after=created_after,
            search=search,
            business_id=business_id,
        )
        total = self.db.scalar(
            select(func.count(PlanExecution.id))
            .join(
                TaskBatch,
                TaskBatch.id == PlanExecution.task_batch_id,
            )
            .outerjoin(
                aggregate,
                aggregate.c.batch_id == TaskBatch.id,
            )
            .where(*filters)
        ) or 0
        rows = self.db.execute(
            _summary_query(aggregate, status_column)
            .where(*filters)
            .order_by(
                PlanExecution.created_at.desc(),
                PlanExecution.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        now = utc_now()
        return [
            _summary_from_row(row, now=now)
            for row in rows
        ], total

    def stats(
        self,
        *,
        test_plan_id: str | None,
        status: ReportStatus | None,
        created_after: datetime | None,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> PlanReportStats:
        aggregate = _task_aggregate()
        status_column = _report_status_expression(aggregate).label(
            "report_status"
        )
        filters = _filters(
            status_column=status_column,
            test_plan_id=test_plan_id,
            status=status,
            created_after=created_after,
            business_id=business_id,
        )
        snapshot_total = func.json_array_length(
            PlanExecution.case_ids_snapshot
        )
        pass_rate_column = case(
            (
                snapshot_total > 0,
                func.coalesce(aggregate.c.pass_count, 0)
                * 100.0
                / snapshot_total,
            ),
            else_=0.0,
        )
        row = self.db.execute(
            select(
                func.count(PlanExecution.id).label("report_count"),
                func.count(PlanExecution.id)
                .filter(status_column == "success")
                .label("success_count"),
                func.count(PlanExecution.id)
                .filter(status_column == "failure")
                .label("failure_count"),
                func.coalesce(
                    func.avg(pass_rate_column),
                    0.0,
                ).label("average_pass_rate"),
            )
            .join(
                TaskBatch,
                TaskBatch.id == PlanExecution.task_batch_id,
            )
            .outerjoin(
                aggregate,
                aggregate.c.batch_id == TaskBatch.id,
            )
            .where(*filters)
        ).one()
        return PlanReportStats(
            report_count=row.report_count or 0,
            success_count=row.success_count or 0,
            failure_count=row.failure_count or 0,
            average_pass_rate=round(row.average_pass_rate or 0.0, 2),
        )

    def get_detail(
        self,
        execution_id: str,
        *,
        page: int,
        page_size: int,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> PlanReportDetail | None:
        aggregate = _task_aggregate()
        status_column = _report_status_expression(aggregate).label(
            "report_status"
        )
        row = self.db.execute(
            _summary_query(aggregate, status_column).where(
                PlanExecution.id == execution_id,
                PlanExecution.business_id == business_id,
            )
        ).one_or_none()
        if row is None:
            return None

        now = utc_now()
        summary = _summary_from_row(row, now=now)
        tasks_total = self.db.scalar(
            select(func.count(Task.id)).where(
                Task.batch_id == row.task_batch_id
            )
        ) or 0
        task_rows = self.db.execute(
            select(
                Task.id.label("task_id"),
                Task.remote_run_id.label("remote_run_id"),
                Task.case_id.label("case_id"),
                TestCase.title.label("case_title"),
                TestCase.deleted_at.label("case_deleted_at"),
                cast(Task.execution_status, String).label(
                    "execution_status"
                ),
                cast(Task.verdict, String).label("verdict"),
                Task.failure_type.label("failure_type"),
                Task.created_at.label("created_at"),
                Task.started_at.label("started_at"),
                Task.finished_at.label("finished_at"),
                Task.result_assets.label("result_assets"),
            )
            .join(TestCase, TestCase.id == Task.case_id)
            .where(Task.batch_id == row.task_batch_id)
            .order_by(Task.batch_position, Task.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        tasks = [
            PlanReportTask(
                task_id=task_row.task_id,
                remote_run_id=task_row.remote_run_id,
                case_id=task_row.case_id,
                case_title=task_row.case_title,
                case_deleted=task_row.case_deleted_at is not None,
                execution_status=_controlled_task_status(
                    task_row.execution_status
                ),
                verdict=_controlled_task_verdict(task_row.verdict),
                failure_type=task_row.failure_type,
                created_at=_as_utc(task_row.created_at),
                started_at=_as_utc(task_row.started_at),
                finished_at=_as_utc(task_row.finished_at),
                duration_seconds=_task_duration_seconds(
                    task_row.result_assets,
                    task_row.started_at,
                    task_row.finished_at,
                    _controlled_task_status(task_row.execution_status),
                    now=now,
                ),
                input_tokens=_usage_int(
                    task_row.result_assets,
                    "in_tokens",
                ),
                output_tokens=_usage_int(
                    task_row.result_assets,
                    "out_tokens",
                ),
                total_steps=_asset_int(
                    task_row.result_assets,
                    "total_steps",
                ),
            )
            for task_row in task_rows
        ]
        return PlanReportDetail(
            **summary.model_dump(),
            plan_tags_snapshot=list(row.plan_tags_snapshot),
            case_ids_snapshot=list(row.case_ids_snapshot),
            device_strategy_snapshot=row.device_strategy_snapshot,
            pod_ids_snapshot=list(row.pod_ids_snapshot),
            concurrency_snapshot=row.concurrency_snapshot,
            runner_type_snapshot=row.runner_type_snapshot,
            config_snapshot=TaskExecutionConfig.model_validate(
                public_execution_config(
                    _with_device_wait_timeout(
                        row.config_snapshot,
                        row.device_wait_timeout_seconds,
                    )
                )
            ),
            pass_count=row.pass_count,
            fail_count=row.fail_count,
            exception_count=row.exception_count,
            cancelled_count=row.cancelled_count,
            queued_count=row.queued_count,
            running_count=row.running_count,
            tasks=tasks,
            tasks_total=tasks_total,
            page=page,
            page_size=page_size,
        )

    def list_plan_executions(
        self,
        plan_id: str,
        *,
        page: int,
        page_size: int,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> tuple[list[PlanReportSummary], int]:
        return self.list_paginated(
            page=page,
            page_size=page_size,
            test_plan_id=plan_id,
            status=None,
            created_after=None,
            business_id=business_id,
        )

    def get_download(
        self,
        execution_id: str,
        *,
        file_format: str,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> tuple[str, str, str] | None:
        detail = self.get_detail(
            execution_id,
            page=1,
            page_size=1,
            business_id=business_id,
        )
        if detail is None:
            return None
        if detail.report_status not in {"success", "failure", "exception"}:
            raise ValueError("task_report_download_unavailable")
        if detail.tasks_total > len(detail.tasks):
            detail = self.get_detail(
                execution_id,
                page=1,
                page_size=max(detail.tasks_total, 1),
                business_id=business_id,
            )
            if detail is None:
                return None

        if file_format == "markdown":
            return (
                _download_markdown(detail),
                "text/markdown; charset=utf-8",
                f"cua-test-report-{detail.task_batch_id}.md",
            )
        if file_format == "csv":
            return (
                _download_csv(detail),
                "text/csv; charset=utf-8",
                f"cua-test-report-{detail.task_batch_id}.csv",
            )
        raise ValueError("unsupported_report_download_format")


def _task_aggregate():
    return (
        select(
            Task.batch_id.label("batch_id"),
            func.count(Task.id).label("task_count"),
            func.count(Task.id)
            .filter(
                Task.execution_status == ExecutionStatus.RESULT_READY,
                Task.verdict == Verdict.PASS,
            )
            .label("pass_count"),
            func.count(Task.id)
            .filter(
                Task.execution_status == ExecutionStatus.RESULT_READY,
                Task.verdict == Verdict.FAIL,
                (
                    Task.failure_type.is_(None)
                    | (Task.failure_type == "assertion_failed")
                ),
            )
            .label("fail_count"),
            func.count(Task.id)
            .filter(
                Task.execution_status == ExecutionStatus.RESULT_READY,
                Task.verdict == Verdict.FAIL,
                Task.failure_type.is_not(None),
                Task.failure_type != "assertion_failed",
            )
            .label("exception_count"),
            func.count(Task.id)
            .filter(Task.execution_status == ExecutionStatus.CANCELLED)
            .label("cancelled_count"),
            func.count(Task.id)
            .filter(Task.execution_status == ExecutionStatus.QUEUED)
            .label("queued_count"),
            func.count(Task.id)
            .filter(Task.execution_status == ExecutionStatus.RUNNING)
            .label("running_count"),
            func.min(Task.started_at).label("started_at"),
            func.max(Task.finished_at).label("finished_at"),
        )
        .where(Task.batch_id.is_not(None))
        .group_by(Task.batch_id)
        .subquery()
    )


def _download_markdown(detail: PlanReportDetail) -> str:
    lines = [
        f"# 测试报告：{detail.plan_name_snapshot}",
        "",
        "## KPI 值",
        f"- 报告ID：{detail.execution_id}",
        f"- 任务批次ID：{detail.task_batch_id}",
        f"- 执行结果：{_report_status_label(detail.report_status)}",
        f"- 测试通过率：{_format_percent(detail.pass_rate)}",
        f"- 通过子任务：{detail.pass_count} / {len(detail.case_ids_snapshot)}",
        f"- 总执行时长：{_format_duration(detail.duration_seconds)}",
        "",
        "## 执行快照",
        f"- 创建时间：{_format_datetime(detail.created_at)}",
        f"- 开始时间：{_format_datetime(detail.started_at)}",
        f"- 完成时间：{_format_datetime(detail.finished_at)}",
        f"- 设备策略：{_device_strategy_label(detail.device_strategy_snapshot)}",
        f"- 并发数：{detail.concurrency_snapshot}",
        f"- Pod：{', '.join(detail.pod_ids_snapshot) if detail.pod_ids_snapshot else '自动分配'}",
        f"- Runner：{detail.runner_type_snapshot}",
        "",
        "## 子任务结果",
        "| 任务 ID | Run ID | 用例 | 状态 | 结果 | 失败类型 | 创建时间 | 执行时长 | 输入 Token | 输出 Token | 执行步数 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for task in detail.tasks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(task.task_id),
                    _md_cell(task.remote_run_id or "-"),
                    _md_cell(f"{task.case_title}（{task.case_id}）"),
                    _md_cell(_task_status_label(task.execution_status)),
                    _md_cell(_task_verdict_label(task.verdict)),
                    _md_cell(task.failure_type or "-"),
                    _md_cell(_format_datetime(task.created_at)),
                    _md_cell(_format_duration(task.duration_seconds)),
                    _md_cell(_format_optional_number(task.input_tokens)),
                    _md_cell(_format_optional_number(task.output_tokens)),
                    _md_cell(_format_optional_number(task.total_steps)),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _download_csv(detail: PlanReportDetail) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["KPI 值"])
    writer.writerow(["报告ID", detail.execution_id])
    writer.writerow(["任务批次ID", detail.task_batch_id])
    writer.writerow(["测试计划", detail.plan_name_snapshot])
    writer.writerow(["执行结果", _report_status_label(detail.report_status)])
    writer.writerow(["测试通过率", _format_percent(detail.pass_rate)])
    writer.writerow(["通过子任务", detail.pass_count])
    writer.writerow(["总子任务", len(detail.case_ids_snapshot)])
    writer.writerow(["总执行时长", _format_duration(detail.duration_seconds)])
    writer.writerow([])
    writer.writerow(["执行快照"])
    writer.writerow(["创建时间", _format_datetime(detail.created_at)])
    writer.writerow(["开始时间", _format_datetime(detail.started_at)])
    writer.writerow(["完成时间", _format_datetime(detail.finished_at)])
    writer.writerow(["设备策略", _device_strategy_label(detail.device_strategy_snapshot)])
    writer.writerow(["并发数", detail.concurrency_snapshot])
    writer.writerow([
        "Pod",
        ", ".join(detail.pod_ids_snapshot) if detail.pod_ids_snapshot else "自动分配",
    ])
    writer.writerow(["Runner", detail.runner_type_snapshot])
    writer.writerow([])
    writer.writerow(["子任务结果"])
    writer.writerow([
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
    ])
    for task in detail.tasks:
        writer.writerow(
            [
                task.task_id,
                task.remote_run_id or "",
                task.case_id,
                task.case_title,
                _task_status_label(task.execution_status),
                _task_verdict_label(task.verdict),
                task.failure_type or "",
                _format_datetime(task.created_at),
                _format_duration(task.duration_seconds),
                _format_optional_number(task.input_tokens),
                _format_optional_number(task.output_tokens),
                _format_optional_number(task.total_steps),
            ]
        )
    return output.getvalue()


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_percent(value: float) -> str:
    return f"{value:g}%"


def _format_duration(value: int | None) -> str:
    if value is None:
        return "-"
    total_seconds = max(0, int(value))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return (
            f"{hours} 小时 {minutes:02d} 分 {seconds:02d} 秒"
        )
    if minutes:
        return f"{minutes} 分 {seconds} 秒"
    return f"{seconds} 秒"


def _format_optional_number(value: int | None) -> str:
    return "-" if value is None else str(value)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _report_status_label(value: ReportStatus) -> str:
    return {
        "queued": "排队中",
        "running": "执行中",
        "success": "成功",
        "failure": "失败",
        "exception": "异常",
        "cancelled": "已取消",
    }[value]


def _task_status_label(value: str) -> str:
    return {
        "script_pending": "脚本待生成",
        "queued": "排队中",
        "running": "执行中",
        "result_ready": "结果已生成",
        "cancelled": "已取消",
        "unknown": "未知",
    }.get(value, "未知")


def _task_verdict_label(value: str | None) -> str:
    return {
        "pass": "通过",
        "fail": "失败",
        "unknown": "未知",
        None: "-",
    }.get(value, "未知")


def _device_strategy_label(value: str) -> str:
    return "自动分配" if value == "automatic" else "指定设备"


def _report_status_expression(aggregate):
    total = func.coalesce(aggregate.c.task_count, 0)
    passed = func.coalesce(aggregate.c.pass_count, 0)
    failed = func.coalesce(aggregate.c.fail_count, 0)
    exceptional = func.coalesce(aggregate.c.exception_count, 0)
    cancelled = func.coalesce(aggregate.c.cancelled_count, 0)
    queued = func.coalesce(aggregate.c.queued_count, 0)
    running = func.coalesce(aggregate.c.running_count, 0)
    terminal = passed + failed + exceptional + cancelled
    batch_status = cast(TaskBatch.execution_status, String)
    batch_verdict = cast(TaskBatch.verdict, String)
    return case(
        (
            (running > 0) | ((queued > 0) & (terminal > 0)),
            "running",
        ),
        (
            (total > 0) & (queued == total),
            "queued",
        ),
        (
            (total > 0) & (terminal == total) & (cancelled == total),
            "cancelled",
        ),
        (
            (total > 0) & (terminal == total) & (exceptional > 0),
            "exception",
        ),
        (
            (total > 0) & (terminal == total) & (failed > 0),
            "failure",
        ),
        (
            (total > 0)
            & (terminal == total)
            & ((batch_verdict == Verdict.PASS.value) | (passed == total)),
            "success",
        ),
        (batch_status == ExecutionStatus.QUEUED.value, "queued"),
        (batch_status == ExecutionStatus.RUNNING.value, "running"),
        (batch_status == ExecutionStatus.CANCELLED.value, "cancelled"),
        (
            (batch_status == ExecutionStatus.RESULT_READY.value)
            & (batch_verdict == Verdict.PASS.value),
            "success",
        ),
        (exceptional > 0, "exception"),
        (
            (batch_status == ExecutionStatus.RESULT_READY.value)
            & (batch_verdict == Verdict.FAIL.value),
            "failure",
        ),
        else_="exception",
    )


def _filters(
    *,
    status_column,
    test_plan_id: str | None,
    status: ReportStatus | None,
    created_after: datetime | None,
    search: str | None = None,
    business_id: str = DEFAULT_BUSINESS_ID,
) -> list:
    filters = [PlanExecution.business_id == business_id]
    if test_plan_id is not None:
        filters.append(PlanExecution.test_plan_id == test_plan_id)
    if status is not None:
        filters.append(status_column == status)
    if created_after is not None:
        filters.append(PlanExecution.created_at >= created_after)
    if search and search.strip():
        filters.append(TaskBatch.id.ilike(f"%{search.strip()}%"))
    return filters


def _summary_query(aggregate, status_column) -> Select:
    return (
        select(
            PlanExecution.id.label("execution_id"),
            PlanExecution.task_batch_id.label("task_batch_id"),
            PlanExecution.test_plan_id.label("test_plan_id"),
            PlanExecution.plan_name_snapshot.label("plan_name_snapshot"),
            PlanExecution.plan_tags_snapshot.label("plan_tags_snapshot"),
            PlanExecution.case_ids_snapshot.label("case_ids_snapshot"),
            PlanExecution.device_strategy_snapshot.label(
                "device_strategy_snapshot"
            ),
            PlanExecution.pod_ids_snapshot.label("pod_ids_snapshot"),
            PlanExecution.concurrency_snapshot.label(
                "concurrency_snapshot"
            ),
            PlanExecution.runner_type_snapshot.label(
                "runner_type_snapshot"
            ),
            PlanExecution.config_snapshot.label("config_snapshot"),
            TaskBatch.device_wait_timeout_seconds.label(
                "device_wait_timeout_seconds"
            ),
            PlanExecution.created_at.label("created_at"),
            func.coalesce(
                aggregate.c.started_at,
                TaskBatch.started_at,
            ).label("started_at"),
            TaskBatch.finished_at.label("finished_at"),
            cast(TaskBatch.execution_status, String).label("batch_status"),
            cast(TaskBatch.verdict, String).label("batch_verdict"),
            status_column,
            func.coalesce(aggregate.c.pass_count, 0).label("pass_count"),
            func.coalesce(aggregate.c.fail_count, 0).label("fail_count"),
            func.coalesce(
                aggregate.c.exception_count,
                0,
            ).label("exception_count"),
            func.coalesce(
                aggregate.c.cancelled_count,
                0,
            ).label("cancelled_count"),
            func.coalesce(
                aggregate.c.queued_count,
                0,
            ).label("queued_count"),
            func.coalesce(
                aggregate.c.running_count,
                0,
            ).label("running_count"),
        )
        .join(
            TaskBatch,
            TaskBatch.id == PlanExecution.task_batch_id,
        )
        .outerjoin(
            aggregate,
            aggregate.c.batch_id == TaskBatch.id,
        )
    )


def _summary_from_row(row, *, now: datetime) -> PlanReportSummary:
    failure_types = (
        {"exception"}
        if row.exception_count
        else {"assertion_failed"} if row.fail_count else set()
    )
    return PlanReportSummary(
        execution_id=row.execution_id,
        task_batch_id=row.task_batch_id,
        test_plan_id=row.test_plan_id,
        plan_name_snapshot=row.plan_name_snapshot,
        report_status=report_status(
            row.batch_status,
            row.batch_verdict,
            failure_types,
            pass_count=row.pass_count,
            fail_count=row.fail_count,
            exception_count=row.exception_count,
            cancelled_count=row.cancelled_count,
            queued_count=row.queued_count,
            running_count=row.running_count,
            total_count=len(row.case_ids_snapshot),
        ),
        pass_rate=pass_rate(
            row.pass_count,
            len(row.case_ids_snapshot),
        ),
        created_at=_as_utc(row.created_at),
        started_at=_as_utc(row.started_at),
        finished_at=_as_utc(row.finished_at),
        duration_seconds=_duration_seconds(
            row.started_at,
            row.finished_at,
            row.batch_status,
            now=now,
        ),
    )


def _duration_seconds(
    started_at: datetime | None,
    finished_at: datetime | None,
    execution_status: str,
    *,
    now: datetime,
) -> int | None:
    if started_at is None:
        return None
    started = _as_utc(started_at)
    if (
        execution_status == ExecutionStatus.RUNNING.value
        and finished_at is None
    ):
        end = now
    elif finished_at is not None:
        end = _as_utc(finished_at)
    else:
        return None
    return max(0, int((end - started).total_seconds()))


def _task_duration_seconds(
    assets: object,
    started_at: datetime | None,
    finished_at: datetime | None,
    execution_status: str,
    *,
    now: datetime,
) -> int | None:
    remote_duration = _remote_duration_seconds(assets)
    if remote_duration is not None:
        return remote_duration
    return _duration_seconds(started_at, finished_at, execution_status, now=now)


def _usage_int(assets: object, key: str) -> int | None:
    if not isinstance(assets, dict):
        return None
    usage = assets.get("usage")
    if not isinstance(usage, dict):
        return None
    return _safe_int(usage.get(key))


def _asset_int(assets: object, key: str) -> int | None:
    if not isinstance(assets, dict):
        return None
    return _safe_int(assets.get(key))


def _remote_duration_seconds(assets: object) -> int | None:
    duration_ms = _asset_int(assets, "duration_ms")
    if duration_ms is None:
        return None
    return max(0, duration_ms // 1000)


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _controlled_task_status(value: str) -> str:
    if value in {status.value for status in ExecutionStatus}:
        return value
    return "unknown"


def _controlled_task_verdict(value: str | None) -> str | None:
    if value is None or value in {verdict.value for verdict in Verdict}:
        return value
    return "unknown"


def _with_device_wait_timeout(
    snapshot: dict,
    device_wait_timeout_seconds: int | None,
) -> dict:
    result = dict(snapshot)
    if (
        "device_wait_timeout_seconds" not in result
        and device_wait_timeout_seconds is not None
    ):
        result["device_wait_timeout_seconds"] = device_wait_timeout_seconds
    return result


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
