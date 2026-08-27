import pytest

from cua_platform.runners.base import RunRequest, RunnerFailure
from cua_platform.runners.mobile_use import MobileUseRunner
from cua_platform.runners.universal_gateway import RemoteRun, UniversalRemoteError
from cua_platform.settings.schemas import RunnerConfig


class CapturingGateway:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def start_one_step(self, _config, payload, *, trace_key=None):
        self.payloads.append(dict(payload))
        return RemoteRun("run-cua", "req-cua", "thread-cua")


class FailingGateway:
    def __init__(self, error: UniversalRemoteError) -> None:
        self.error = error

    async def start_one_step(self, _config, _payload, *, trace_key=None):
        raise self.error


class MissingRunIdGateway:
    async def start_one_step(self, _config, _payload, *, trace_key=None):
        raise UniversalRemoteError(
            "response_invalid",
            "req-missing-run-id",
            retryable=False,
            response_received=True,
        )


def cua_config() -> RunnerConfig:
    return RunnerConfig(
        mode="mobile_use",
        access_key_id="ak",
        secret_access_key="sk",
        account_id="2103274899",
        pod_id="i-yeguephgqobw80d94vdf",
        tos_bucket="bucket",
        tos_region="cn-beijing",
    )


@pytest.mark.asyncio
async def test_cua_runner_starts_one_step_with_ecsid_and_agent_type():
    gateway = CapturingGateway()
    runner = MobileUseRunner(
        cua_config(),
        gateway,  # type: ignore[arg-type]
        request_loader=lambda _task_id: None,
    )

    handle = await runner.start(
        RunRequest(
            task_id="task_1",
            scenario="打开网页",
            title="打开网页",
            content_markdown="- 打开浏览器",
        ),
        idempotency_key="idem-1",
    )

    assert handle.run_id == "run-cua"
    assert gateway.payloads
    payload = gateway.payloads[0]
    assert payload["AgentType"] == "cua"
    assert payload["Ecsid"] == "i-yeguephgqobw80d94vdf"
    assert "PodId" not in payload
    assert "ProductId" not in payload
    assert "UseBase64Screenshot" not in payload
    assert "IsScreenRecord" not in payload


@pytest.mark.asyncio
async def test_cua_runner_omits_tos_fields_when_not_configured():
    gateway = CapturingGateway()
    runner = MobileUseRunner(
        RunnerConfig(
            mode="mobile_use",
            access_key_id="ak",
            secret_access_key="sk",
            account_id="2103274899",
            pod_id="i-yeguephgqobw80d94vdf",
        ),
        gateway,  # type: ignore[arg-type]
        request_loader=lambda _task_id: None,
    )

    await runner.start(
        RunRequest(
            task_id="task_1",
            scenario="打开网页",
            title="打开网页",
            content_markdown="- 打开浏览器",
        ),
        idempotency_key="idem-1",
    )

    payload = gateway.payloads[0]
    assert "TosBucket" not in payload
    assert "TosEndpoint" not in payload
    assert "TosRegion" not in payload


@pytest.mark.asyncio
async def test_cua_runner_marks_transport_start_failure_outcome_unknown():
    runner = MobileUseRunner(
        cua_config(),
        FailingGateway(
            UniversalRemoteError(
                "remote_timeout",
                None,
                retryable=True,
                response_received=False,
            )
        ),  # type: ignore[arg-type]
        request_loader=lambda _task_id: None,
    )

    with pytest.raises(RunnerFailure) as caught:
        await runner.start(
            RunRequest("task_1", "success", "title", "- step"),
            idempotency_key="idem-transport",
        )

    assert caught.value.start_outcome_unknown is True


@pytest.mark.asyncio
async def test_cua_runner_marks_missing_run_id_outcome_unknown():
    runner = MobileUseRunner(
        cua_config(),
        MissingRunIdGateway(),  # type: ignore[arg-type]
        request_loader=lambda _task_id: None,
    )

    with pytest.raises(RunnerFailure) as caught:
        await runner.start(
            RunRequest("task_1", "success", "title", "- step"),
            idempotency_key="idem-missing-run-id",
        )

    assert caught.value.start_outcome_unknown is True


@pytest.mark.asyncio
async def test_cua_runner_keeps_preflight_start_failure_known():
    runner = MobileUseRunner(
        cua_config().model_copy(update={"pod_id": None}),
        CapturingGateway(),  # type: ignore[arg-type]
        request_loader=lambda _task_id: None,
    )

    with pytest.raises(RunnerFailure) as caught:
        await runner.start(
            RunRequest("task_1", "success", "title", "- step"),
            idempotency_key="idem-preflight",
        )

    assert caught.value.start_outcome_unknown is False


@pytest.mark.asyncio
async def test_cua_runner_keeps_remote_rejection_start_failure_known():
    runner = MobileUseRunner(
        cua_config(),
        FailingGateway(
            UniversalRemoteError(
                "invalid_parameter",
                "req-rejected",
                retryable=False,
                response_received=True,
            )
        ),  # type: ignore[arg-type]
        request_loader=lambda _task_id: None,
    )

    with pytest.raises(RunnerFailure) as caught:
        await runner.start(
            RunRequest("task_1", "success", "title", "- step"),
            idempotency_key="idem-rejected",
        )

    assert caught.value.start_outcome_unknown is False
