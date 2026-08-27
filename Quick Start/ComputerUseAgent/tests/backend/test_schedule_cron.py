from datetime import UTC, datetime

import pytest

from cua_platform.test_plans.scheduling import (
    compute_next_run,
    describe_cron,
    preview_next_runs,
    validate_cron,
)


def test_validate_cron_accepts_standard_five_field():
    validate_cron("0 9 * * 1-5")
    validate_cron("*/5 * * * *")
    validate_cron("0 0 1 1 *")


def test_validate_cron_rejects_invalid():
    with pytest.raises(ValueError, match="invalid_cron"):
        validate_cron("not a cron")
    with pytest.raises(ValueError, match="invalid_cron"):
        validate_cron("0 9 * *")
    with pytest.raises(ValueError, match="invalid_cron"):
        validate_cron("60 9 * * *")


def test_validate_cron_rejects_six_field_seconds():
    with pytest.raises(ValueError, match="invalid_cron"):
        validate_cron("0 0 9 * * 1-5")


def test_compute_next_run_returns_utc():
    after = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    result = compute_next_run("0 9 * * *", "Asia/Shanghai", after)
    assert result == datetime(2026, 8, 26, 1, 0, tzinfo=UTC)


def test_compute_next_run_weekday():
    after = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    result = compute_next_run("0 9 * * 1-5", "UTC", after)
    assert result.weekday() == 2
    assert result.hour == 9


def test_compute_next_run_every_15_minutes():
    after = datetime(2026, 8, 25, 10, 7, tzinfo=UTC)
    result = compute_next_run("*/15 * * * *", "UTC", after)
    assert result.minute == 15
    assert result.hour == 10


def test_preview_next_runs_returns_count():
    after = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    results = preview_next_runs("0 9 * * *", "UTC", after, count=3)
    assert len(results) == 3
    assert results[0] < results[1] < results[2]


def test_preview_next_runs_default_count():
    after = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    results = preview_next_runs("0 9 * * *", "UTC", after)
    assert len(results) == 5


def test_compute_next_run_invalid_timezone():
    after = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="invalid_timezone"):
        compute_next_run("0 9 * * *", "Not/AZone", after)


def test_describe_cron_daily():
    desc = describe_cron("0 9 * * *")
    assert "每天" in desc
    assert "09:00" in desc


def test_describe_cron_weekday():
    desc = describe_cron("0 9 * * 1-5")
    assert "工作日" in desc


def test_describe_cron_every_15_minutes():
    desc = describe_cron("*/15 * * * *")
    assert "15" in desc


def test_describe_cron_custom():
    desc = describe_cron("30 3 1 6 *")
    assert "自定义" in desc
