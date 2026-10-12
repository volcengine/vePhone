import pytest
from pydantic import ValidationError

from cua_platform.settings.schemas import (
    AgentRuntimeOptions,
    RunnerConfig,
    RunnerExecutionSettingsError,
)
from cua_platform.tasks.execution_config import public_execution_config


def test_cua_execution_snapshot_requires_account_not_product_or_tos():
    config = RunnerConfig(
        mode="mobile_use",
        access_key_id="AKLT00000000WXYZ",
        secret_access_key="secret-value",
        account_id="2103274899",
    )

    snapshot = config.execution_snapshot()

    assert snapshot["account_id"] == "2103274899"
    assert "product_id" not in snapshot
    assert "tos_bucket" not in snapshot
    assert "tos_region" not in snapshot


def test_cua_execution_snapshot_reports_missing_account_id():
    config = RunnerConfig(
        mode="mobile_use",
        access_key_id="AKLT00000000WXYZ",
        secret_access_key="secret-value",
    )

    with pytest.raises(RunnerExecutionSettingsError) as exc_info:
        config.execution_snapshot()

    assert exc_info.value.missing_fields == ["account_id"]


def test_agent_runtime_options_accepts_script_asset_binding():
    options = AgentRuntimeOptions(run_mode="ScriptRun", script_id=1001)

    assert options.model_dump(exclude_none=True) == {
        "run_mode": "ScriptRun",
        "script_id": 1001,
    }


def test_agent_runtime_options_accepts_chain_asset_binding():
    options = AgentRuntimeOptions(run_mode="ChainRun", chain_id=2001)

    assert options.model_dump(exclude_none=True) == {
        "run_mode": "ChainRun",
        "chain_id": 2001,
    }


def test_agent_runtime_options_rejects_mixed_asset_binding():
    with pytest.raises(ValidationError) as exc_info:
        AgentRuntimeOptions(run_mode="ScriptRun", script_id=1001, chain_id=2001)

    assert "script_run_requires_only_script_id" in str(exc_info.value)


def test_runner_config_snapshot_keeps_asset_binding():
    config = RunnerConfig(
        mode="mobile_use",
        access_key_id="AKLT00000000WXYZ",
        secret_access_key="secret-value",
        account_id="2103274899",
        run_mode="ChainRun",
        chain_id=2001,
    )

    snapshot = config.execution_snapshot()
    restored = config.with_execution_snapshot(snapshot)

    assert snapshot["run_mode"] == "ChainRun"
    assert snapshot["chain_id"] == 2001
    assert restored.run_mode == "ChainRun"
    assert restored.chain_id == 2001


def test_runner_config_snapshot_revalidates_asset_binding():
    config = RunnerConfig(
        mode="mobile_use",
        access_key_id="AKLT00000000WXYZ",
        secret_access_key="secret-value",
        account_id="2103274899",
    )

    with pytest.raises(ValidationError) as exc_info:
        config.with_execution_snapshot({"run_mode": "ScriptRun"})

    assert "script_run_requires_only_script_id" in str(exc_info.value)


def test_public_execution_config_exposes_asset_binding():
    public = public_execution_config(
        {
            "config_source": "custom",
            "account_id": "2103274899",
            "run_mode": "ScriptRun",
            "script_id": 1001,
        }
    )

    assert public["source"] == "custom"
    assert public["run_mode"] == "ScriptRun"
    assert public["script_id"] == 1001
    assert public["chain_id"] is None
