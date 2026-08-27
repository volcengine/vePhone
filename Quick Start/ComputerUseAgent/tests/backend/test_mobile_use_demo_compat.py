from cua_platform.runners.mobile_use_parser import (
    parse_agent_result,
    step_status_is_terminal,
)


def test_demo_style_status_reason_struct_output_is_supported():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "StructOutput": {
                "status": "fail",
                "reason": "首页断言失败",
                "evidence": ["页面未出现首页"],
            },
        }
    )

    assert parsed.remote_terminal is True
    assert parsed.verdict == "fail"
    assert parsed.failure_type == "assertion_failed"
    assert parsed.summary == "首页断言失败"
    assert parsed.evidence == ("页面未出现首页",)


def test_markdown_fenced_json_content_is_parsed_with_result_assets():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "Content": """```json
{
  "verdict": "pass",
  "summary": "已成功打开抖音并查看视频",
  "evidence": ["打开抖音成功", "已查看三个视频"]
}
```""",
            "ScreenShots": {
                "shot-1": {"screenshot": "https://example.invalid/shot.png"}
            },
            "Usage": {"in_tokens": 123, "out_tokens": 45},
            "TotalSteps": 4,
            "DurationMs": 72000,
            "DurationFmt": "1m12s",
            "AvgStepDurationSec": 18,
        }
    )

    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.summary == "已成功打开抖音并查看视频"
    assert parsed.evidence == ("打开抖音成功", "已查看三个视频")
    assert parsed.result_assets["usage"] == {"in_tokens": 123, "out_tokens": 45}
    assert "shot-1" in parsed.result_assets["screenshots"]
    assert parsed.result_assets["total_steps"] == 4
    assert parsed.result_assets["duration_ms"] == 72000
    assert parsed.result_assets["duration_fmt"] == "1m12s"
    assert parsed.result_assets["avg_step_duration_sec"] == 18


def test_malformed_fenced_json_content_keeps_explicit_pass_evidence():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "Content": """页面中的图片清晰可见。

```json
{
  "verdict": "pass",
  "summary": "成功打开 WPS 文档页面并查看到图片。",
  "evidence": [
    "证据1：页面标题为"文字文稿"，确认成功打开目标页面",
    "证据2：页面出现弹窗"Inviting you to log in"，点击 X 后关闭"
  ]
}
```""",
        }
    )

    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.summary == "成功打开 WPS 文档页面并查看到图片。"
    assert parsed.evidence == (
        '证据1：页面标题为"文字文稿"，确认成功打开目标页面',
        '证据2：页面出现弹窗"Inviting you to log in"，点击 X 后关闭',
    )


def test_unstructured_content_is_preserved_as_failed_evidence():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "Content": "任务执行完成，但没有返回结构化 JSON。",
            "Usage": {"in_tokens": 20, "out_tokens": 8},
        }
    )

    assert parsed.verdict == "fail"
    assert parsed.failure_type == "evidence_missing"
    assert parsed.summary == "任务执行完成，但没有返回结构化 JSON。"
    assert parsed.result_assets["content"] == "任务执行完成，但没有返回结构化 JSON。"


def test_completed_without_content_is_remote_success_with_no_message():
    parsed = parse_agent_result({"IsSuccess": 3})

    assert parsed.remote_terminal is True
    assert parsed.remote_state == "completed_no_message"
    assert parsed.remote_status_code == 3
    assert parsed.verdict == "fail"
    assert parsed.failure_type == "completed_but_no_message"
    assert parsed.summary == "执行成功，但未返回 Content。"


def test_completed_current_step_status_is_terminal():
    assert step_status_is_terminal({"Status": 3, "Results": []}) is True
