from cua_platform.runners.mobile_use_parser import (
    parse_agent_result,
    step_status_is_terminal,
)


def test_remote_success_ignores_struct_output_failure_status():
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
    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
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


def test_remote_success_with_unstructured_content_passes():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "Content": "任务执行完成，但没有返回结构化 JSON。",
            "Usage": {"in_tokens": 20, "out_tokens": 8},
        }
    )

    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.evidence_complete is True
    assert parsed.summary == "任务执行完成，但没有返回结构化 JSON。"
    assert parsed.evidence == ("任务执行完成，但没有返回结构化 JSON。",)
    assert parsed.result_assets["content"] == "任务执行完成，但没有返回结构化 JSON。"


def test_completed_without_content_is_remote_success_with_no_message():
    parsed = parse_agent_result({"IsSuccess": 3})

    assert parsed.remote_terminal is True
    assert parsed.remote_state == "completed_no_message"
    assert parsed.remote_status_code == 3
    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.evidence_complete is True
    assert parsed.summary == "执行成功，但未返回 Content。"


def test_output_schema_style_succeeded_result_passes_with_extracted_evidence():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "StructOutput": {
                "status": "succeeded",
                "summary": "已完成目标视频的点赞和评论",
                "data": {
                    "stopReason": "已完成1条目标视频互动",
                    "candidates": [
                        {
                            "nickname": "林川讲大健康",
                            "stage": "delivered_waiting",
                            "sourceContent": "大健康领域视频",
                        }
                    ],
                    "reaches": [
                        {
                            "contact": "林川讲大健康",
                            "channel": "comment",
                            "actions": ["like", "comment"],
                            "result": "delivered",
                            "scriptContent": "讲的太实用了！",
                        }
                    ],
                    "conversations": [],
                    "obstacles": [],
                },
            },
        }
    )

    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.evidence_complete is True
    assert parsed.summary == "已完成目标视频的点赞和评论"
    joined = "\n".join(parsed.evidence)
    assert "已完成1条目标视频互动" in joined
    assert "林川讲大健康" in joined
    assert "like/comment" in joined


def test_remote_success_ignores_output_schema_partial_status():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "StructOutput": {
                "status": "partial",
                "summary": "只完成点赞，未评论",
                "data": {
                    "stopReason": "评论受限",
                    "candidates": [{"nickname": "博主A", "stage": "reached_failed"}],
                    "reaches": [
                        {
                            "contact": "博主A",
                            "channel": "comment",
                            "actions": ["like"],
                            "failReason": "评论被限流",
                        }
                    ],
                    "conversations": [],
                    "obstacles": [{"blockReason": "评论受限", "detail": "账号无评论权限"}],
                },
            },
        }
    )

    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.evidence_complete is True
    joined = "\n".join(parsed.evidence)
    assert "评论受限" in joined
    assert "博主A" in joined


def test_remote_success_ignores_output_schema_failed_status():
    parsed = parse_agent_result(
        {
            "IsSuccess": 1,
            "StructOutput": {
                "status": "failed",
                "summary": "未找到目标视频",
                "data": {
                    "stopReason": "无候选",
                    "candidates": [],
                    "reaches": [],
                    "conversations": [],
                    "obstacles": [{"blockReason": "搜索无结果"}],
                },
            },
        }
    )

    assert parsed.verdict == "pass"
    assert parsed.failure_type is None
    assert parsed.evidence_complete is True
    assert "搜索无结果" in "\n".join(parsed.evidence)


def test_completed_current_step_status_is_terminal():
    assert step_status_is_terminal({"Status": 3, "Results": []}) is True
