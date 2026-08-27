import asyncio
import os
from dataclasses import replace
from pathlib import Path

from mua_platform.main import create_app
from mua_platform.runners.base import PollResult, RunnerEvent
from mua_platform.runners.mock import MockRunner


class ControlledRunner(MockRunner):
    async def start(self, request, idempotency_key):
        normalized = replace(
            request,
            steps=request.steps
            or [{"index": 1, "instruction": request.content_markdown}],
            assertions=request.assertions or [],
        )
        handle = await super().start(normalized, idempotency_key)
        start_log = os.environ.get("E2E_RUNNER_START_LOG")
        if start_log:
            with Path(start_log).open("a", encoding="utf-8") as stream:
                stream.write(f"{request.task_id} {handle.run_id}\n")
        return handle

    async def poll(self, handle, after_sequence):
        hold_file = Path(os.environ["E2E_RUNNER_HOLD_FILE"])
        request = self._request_from_handle(handle)
        if not hold_file.exists():
            page = await super().poll(handle, after_sequence)
            return PollResult(
                events=tuple(
                    _terminal_event(event, request.scenario)
                    for event in page.events
                ),
                terminal=page.terminal,
            )

        page = await super().poll(handle, after_sequence)
        if after_sequence == 0:
            return PollResult(events=page.events[:1], terminal=False)

        while hold_file.exists():
            await asyncio.sleep(0.05)

        return PollResult(events=page.events[:1], terminal=False)


def _terminal_event(event: RunnerEvent, scenario: str) -> RunnerEvent:
    if event.type != "task_finished":
        return event
    outcomes = {
        "success": {
            "verdict": "pass",
            "evidence_complete": True,
        },
        "assertion_failure": {
            "verdict": "fail",
            "failure_type": "assertion_failed",
            "evidence_complete": True,
        },
        "evidence_missing": {
            "verdict": "fail",
            "failure_type": "evidence_missing",
            "evidence_complete": False,
        },
    }
    return RunnerEvent(
        sequence=event.sequence,
        type=event.type,
        payload=outcomes[scenario],
    )


app = create_app(
    runner_factory=lambda _task, _config, _request_loader: ControlledRunner(
        os.environ["APP_SECRET_KEY"],
    )
)
