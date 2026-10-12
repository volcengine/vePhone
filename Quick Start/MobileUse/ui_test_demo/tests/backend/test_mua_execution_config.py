import pytest
from pydantic import ValidationError

from mua_platform.settings.schemas import (
    AgentRuntimeOptions,
    RunnerConfig,
)
from mua_platform.tasks.execution_config import public_execution_config


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
        product_id="product-assets",
        tos_bucket="assets-bucket",
        tos_region="cn-beijing",
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
        product_id="product-assets",
        tos_bucket="assets-bucket",
        tos_region="cn-beijing",
    )

    with pytest.raises(ValidationError) as exc_info:
        config.with_execution_snapshot({"run_mode": "ScriptRun"})

    assert "script_run_requires_only_script_id" in str(exc_info.value)


def test_public_execution_config_exposes_asset_binding():
    public = public_execution_config(
        {
            "config_source": "custom",
            "product_id": "product-assets",
            "run_mode": "ScriptRun",
            "script_id": 1001,
        }
    )

    assert public["source"] == "custom"
    assert public["run_mode"] == "ScriptRun"
    assert public["script_id"] == 1001
    assert public["chain_id"] is None
