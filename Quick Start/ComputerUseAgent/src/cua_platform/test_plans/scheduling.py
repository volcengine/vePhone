from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

_CRON_FIELD_COUNT = 5


def validate_cron(expr: str) -> None:
    parts = expr.strip().split()
    if len(parts) != _CRON_FIELD_COUNT:
        raise ValueError("invalid_cron")
    if not croniter.is_valid(expr):
        raise ValueError("invalid_cron")


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("invalid_timezone") from exc


def compute_next_run(
    cron_expr: str,
    timezone_name: str,
    after: datetime,
) -> datetime:
    validate_cron(cron_expr)
    tz = _zone(timezone_name)
    local_after = after.astimezone(tz)
    cron = croniter(cron_expr, local_after)
    next_local = cron.get_next(datetime)
    return next_local.astimezone(UTC)


def preview_next_runs(
    cron_expr: str,
    timezone_name: str,
    after: datetime,
    count: int = 5,
) -> list[datetime]:
    validate_cron(cron_expr)
    tz = _zone(timezone_name)
    local_after = after.astimezone(tz)
    cron = croniter(cron_expr, local_after)
    results: list[datetime] = []
    for _ in range(count):
        next_local = cron.get_next(datetime)
        results.append(next_local.astimezone(UTC))
    return results


def describe_cron(cron_expr: str) -> str:
    validate_cron(cron_expr)
    minute, hour, _day, _month, weekday = cron_expr.split()
    if minute.startswith("*/"):
        return f"每 {minute[2:]} 分钟"
    if minute.isdigit() and hour.isdigit():
        time_str = f"{int(hour):02d}:{int(minute):02d}"
        if weekday == "1-5":
            return f"工作日 {time_str}"
        if weekday == "*" and _day == "*":
            return f"每天 {time_str}"
    return f"自定义（{cron_expr}）"
