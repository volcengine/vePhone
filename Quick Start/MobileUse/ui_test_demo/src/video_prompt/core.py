from __future__ import annotations

import argparse
from typing import Optional, Tuple
import base64
import binascii
import datetime
import logging
import mimetypes
import os
import re
import secrets
import time
from pathlib import Path

try:
    from volcenginesdkarkruntime import Ark
    from volcenginesdkarkruntime._exceptions import ArkBadRequestError, ArkAPIError
except Exception:
    Ark = None  # type: ignore
    ArkBadRequestError = Exception  # type: ignore
    ArkAPIError = Exception  # type: ignore


logger = logging.getLogger(__name__)


VIDEO_ANALYSIS_PROMPT = """
我需要做一些OS里的重复操作，视频是其中一个操作录屏，请解析这个视频，输出详细操作步骤，用来指导Mobile Use Agent复刻这一操作。

请按照以下格式输出：

## 操作目标
[描述视频中要完成的任务]

## 操作步骤
1. [第一步操作]
2. [第二步操作]
3. [继续列出所有步骤]

## 注意事项
- [重要的操作注意点]
- [可能遇到的问题和解决方案]

请确保指导清晰、准确、易于执行。
""".strip()


def extract_video_url_from_case_text(text: str) -> Tuple[Optional[str], str]:
    if not isinstance(text, str) or not text.strip():
        return None, ""

    url: Optional[str] = None
    kept: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^(video_url|video-url|video)\s*[:=]\s*(\S+)\s*$", line, flags=re.IGNORECASE)
        if m and url is None:
            candidate = (m.group(2) or "").strip()
            if candidate.startswith("http"):
                url = candidate
                continue
        kept.append(raw)

    return url, "\n".join(kept).strip()


def _required_env(name: str) -> Tuple[Optional[str], Optional[str]]:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v, None
    return None, f"缺少环境变量 {name}"


def _normalize_recording_id(recording_id: Optional[str]) -> str:
    rid = (recording_id or "").strip()
    if rid:
        return rid
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{ts}{secrets.token_hex(4)}"


def _extract_response_text(resp: object) -> str:
    output_text = getattr(resp, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    pieces: list[str] = []

    output = getattr(resp, "output", None)
    if isinstance(output, list):
        for item in output:
            content = getattr(item, "content", None)
            if isinstance(item, dict):
                content = item.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                text = getattr(c, "text", None)
                if isinstance(c, dict):
                    text = c.get("text")
                if isinstance(text, str) and text.strip():
                    pieces.append(text.strip())

    if pieces:
        return "\n".join(pieces).strip()

    choices = getattr(resp, "choices", None)
    if isinstance(choices, list) and choices:
        first = choices[0]
        message = getattr(first, "message", None)
        if isinstance(first, dict):
            message = first.get("message")
        content = getattr(message, "content", None) if message is not None else None
        if isinstance(message, dict):
            content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    return ""


def _strip_data_url_prefix(b64: str) -> str:
    v = (b64 or "").strip()
    if not v:
        return ""
    if v.startswith("data:"):
        comma = v.find(",")
        if comma >= 0:
            return v[comma + 1 :].strip()
    return v


def _file_to_video_data_url_base64(path: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return None, f"读取视频文件失败: {path}"

    mime, _ = mimetypes.guess_type(path)
    if not isinstance(mime, str) or not mime.strip():
        mime = "video/mp4"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}", None


def _upload_video_file_and_get_id(
    *,
    client: object,
    video_file: object,
    fps: float,
) -> Tuple[Optional[str], Optional[str]]:
    files_api = getattr(client, "files", None)
    if files_api is None:
        return None, "当前 Ark Runtime 不支持 Files API（client.files 不存在）"

    create = getattr(files_api, "create", None)
    if create is None:
        return None, "当前 Ark Runtime 不支持 Files API（client.files.create 不存在）"

    preprocess_configs = {"video": {"fps": float(fps)}}
    try:
        file_obj = create(file=video_file, purpose="user_data", preprocess_configs=preprocess_configs)
    except TypeError:
        file_obj = create(file=video_file, purpose="user_data")

    file_id = getattr(file_obj, "id", None)
    if isinstance(file_obj, dict):
        file_id = file_obj.get("id")
    if not isinstance(file_id, str) or not file_id.strip():
        return None, "Files API 上传成功但未获取到 file_id"

    wait_for_processing = getattr(files_api, "wait_for_processing", None)
    if callable(wait_for_processing):
        wait_for_processing(file_id)
        return file_id, None

    retrieve = getattr(files_api, "retrieve", None)
    if not callable(retrieve):
        return file_id, None

    start = time.time()
    while time.time() - start < 180:
        info = retrieve(file_id)
        status = getattr(info, "status", None)
        if isinstance(info, dict):
            status = info.get("status")
        if isinstance(status, str) and status.lower() != "processing":
            break
        time.sleep(2)
    return file_id, None


def generate_prompt_from_video_file_id(
    *,
    file_id: str,
    recording_id: str,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> Tuple[Optional[str], Optional[str]]:
    fid = (file_id or "").strip()
    if not fid:
        return None, "file_id 为空"

    if Ark is None:
        return None, "未安装 Ark Runtime：请安装 volcengine-python-sdk[ark]"

    ark_base_url, err = _required_env("ARK_BASE_URL")
    if err:
        return None, err
    ark_api_key, err = _required_env("ARK_API_KEY")
    if err:
        return None, err
    ark_model_id, err = _required_env("ARK_MODEL_ID")
    if err:
        return None, err

    try:
        client = Ark(base_url=ark_base_url, api_key=ark_api_key)
        responses_api = getattr(client, "responses", None)
        if responses_api is None or not hasattr(responses_api, "create"):
            return None, "当前 Ark Runtime 不支持 Responses API（client.responses.create 不存在）"

        input_items = [
            {
                "role": "user",
                "content": [
                    {"type": "input_video", "file_id": fid},
                    {"type": "input_text", "text": str(prompt_template or VIDEO_ANALYSIS_PROMPT)},
                ],
            }
        ]
        resp = responses_api.create(model=ark_model_id, input=input_items)
        out = _extract_response_text(resp)
        if not out:
            return None, "模型返回为空"
        return out, None
    except ArkBadRequestError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 请求错误 recording_id={recording_id}: {msg}")
        return None, f"视频生成 prompt 请求错误: {msg}"
    except ArkAPIError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 服务错误 recording_id={recording_id}: {msg}")
        return None, "视频生成 prompt 服务暂不可用"
    except Exception as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 未知错误 recording_id={recording_id}: {type(e).__name__}: {msg}")
        return None, f"视频生成 prompt 未知错误: {type(e).__name__}: {msg}"


def generate_prompt_from_video_path(
    *,
    video_path: str,
    video_path_mode: str = "file",
    recording_id: str,
    fps: int = 2,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> Tuple[Optional[str], Optional[str], str]:
    path = (video_path or "").strip()
    if not path:
        return None, "video_path 为空", ""
    if not os.path.exists(path):
        return None, f"video_path 不存在: {path}", ""

    fps_int = 2
    try:
        fps_int = int(fps)
    except Exception:
        fps_int = 2
    fps_int = min(10, max(1, fps_int))

    mode = (video_path_mode or "file").strip().lower()
    if mode not in ("file", "base64"):
        return None, f"video_path_mode 不支持: {video_path_mode}", ""
    if mode == "base64":
        data_url, err = _file_to_video_data_url_base64(path)
        if err:
            return None, err, ""
        prompt, err2 = generate_prompt_from_video_base64(
            video_base64=str(data_url),
            recording_id=recording_id,
            fps=fps_int,
            prompt_template=prompt_template,
        )
        return prompt, err2, ""

    if Ark is None:
        return None, "未安装 Ark Runtime：请安装 volcengine-python-sdk[ark]", ""

    ark_base_url, err = _required_env("ARK_BASE_URL")
    if err:
        return None, err, ""
    ark_api_key, err = _required_env("ARK_API_KEY")
    if err:
        return None, err, ""

    try:
        client = Ark(base_url=ark_base_url, api_key=ark_api_key)
        with open(path, "rb") as f:
            file_id, err = _upload_video_file_and_get_id(client=client, video_file=f, fps=float(fps_int))
        if err:
            return None, err, ""
        prompt, err2 = generate_prompt_from_video_file_id(
            file_id=str(file_id),
            recording_id=recording_id,
            prompt_template=prompt_template,
        )
        return prompt, err2, str(file_id)
    except ArkBadRequestError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 请求错误 recording_id={recording_id}: {msg}")
        return None, f"视频生成 prompt 请求错误: {msg}", ""
    except ArkAPIError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 服务错误 recording_id={recording_id}: {msg}")
        return None, "视频生成 prompt 服务暂不可用", ""
    except Exception as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 未知错误 recording_id={recording_id}: {type(e).__name__}: {msg}")
        return None, f"视频生成 prompt 未知错误: {type(e).__name__}: {msg}", ""


def generate_prompt_from_video_base64(
    *,
    video_base64: str,
    recording_id: str,
    fps: int = 2,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> Tuple[Optional[str], Optional[str]]:
    raw_input = (video_base64 or "").strip()
    if not raw_input:
        return None, "video_base64 为空"

    fps_int = 2
    try:
        fps_int = int(fps)
    except Exception:
        fps_int = 2
    fps_int = min(10, max(1, fps_int))

    url = ""
    if raw_input.startswith("data:"):
        url = re.sub(r"\s+", "", raw_input)
    else:
        raw = re.sub(r"\s+", "", _strip_data_url_prefix(raw_input))
        if not raw:
            return None, "video_base64 为空"
        try:
            padded = raw + ("=" * (-len(raw) % 4))
            base64.b64decode(padded, validate=True)
        except binascii.Error:
            return None, "video_base64 解码失败"
        url = f"data:video/mp4;base64,{raw}"

    if Ark is None:
        return None, "未安装 Ark Runtime：请安装 volcengine-python-sdk[ark]"

    ark_base_url, err = _required_env("ARK_BASE_URL")
    if err:
        return None, err
    ark_api_key, err = _required_env("ARK_API_KEY")
    if err:
        return None, err
    ark_model_id, err = _required_env("ARK_MODEL_ID")
    if err:
        return None, err

    try:
        client = Ark(base_url=ark_base_url, api_key=ark_api_key)
        resp = client.chat.completions.create(
            model=ark_model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "video_url", "video_url": {"url": url, "fps": fps_int}},
                        {"type": "text", "text": str(prompt_template or VIDEO_ANALYSIS_PROMPT)},
                    ],
                }
            ],
            max_tokens=4096,
            temperature=0.1,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = resp.choices[0].message.content
        out = content.strip() if isinstance(content, str) else ""
        if not out:
            return None, "模型返回为空"
        return out, None
    except ArkBadRequestError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 请求错误 recording_id={recording_id}: {msg}")
        return None, f"视频生成 prompt 请求错误: {msg}"
    except ArkAPIError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 服务错误 recording_id={recording_id}: {msg}")
        return None, "视频生成 prompt 服务暂不可用"
    except Exception as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 未知错误 recording_id={recording_id}: {type(e).__name__}: {msg}")
        return None, f"视频生成 prompt 未知错误: {type(e).__name__}: {msg}"


def generate_prompt_from_video(
    *,
    video_url: Optional[str] = None,
    video_path: Optional[str] = None,
    video_path_mode: str = "file",
    video_base64: Optional[str] = None,
    video_file_id: Optional[str] = None,
    recording_id: Optional[str] = None,
    fps: int = 2,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> Tuple[Optional[str], Optional[str], str, str]:
    rid = _normalize_recording_id(recording_id)

    provided = [bool((video_url or "").strip()), bool((video_path or "").strip()), bool((video_base64 or "").strip()), bool((video_file_id or "").strip())]
    if sum(1 for v in provided if v) != 1:
        return None, "需要且只能提供一种视频输入：video_url/video_path/video_base64/video_file_id", rid, ""

    if (video_url or "").strip():
        prompt, err = generate_prompt_from_video_url(
            video_url=str(video_url),
            recording_id=rid,
            fps=fps,
            prompt_template=prompt_template,
        )
        return prompt, err, rid, ""

    if (video_path or "").strip():
        prompt, err, fid = generate_prompt_from_video_path(
            video_path=str(video_path),
            video_path_mode=video_path_mode,
            recording_id=rid,
            fps=fps,
            prompt_template=prompt_template,
        )
        return prompt, err, rid, fid

    if (video_base64 or "").strip():
        prompt, err = generate_prompt_from_video_base64(
            video_base64=str(video_base64),
            recording_id=rid,
            fps=fps,
            prompt_template=prompt_template,
        )
        return prompt, err, rid, ""

    prompt, err = generate_prompt_from_video_file_id(
        file_id=str(video_file_id),
        recording_id=rid,
        prompt_template=prompt_template,
    )
    return prompt, err, rid, (video_file_id or "").strip()


def generate_prompt_from_video_url(
    *,
    video_url: str,
    recording_id: str,
    fps: int = 2,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> Tuple[Optional[str], Optional[str]]:
    url = (video_url or "").strip()
    if not url:
        return None, "video_url 为空"
    if not url.startswith("http"):
        return None, "video_url 格式不正确，需要 http/https URL"

    if Ark is None:
        return None, "未安装 Ark Runtime：请安装 volcengine-python-sdk[ark]"

    ark_base_url, err = _required_env("ARK_BASE_URL")
    if err:
        return None, err
    ark_api_key, err = _required_env("ARK_API_KEY")
    if err:
        return None, err
    ark_model_id, err = _required_env("ARK_MODEL_ID")
    if err:
        return None, err

    fps_int = 2
    try:
        fps_int = int(fps)
    except Exception:
        fps_int = 2
    fps_int = min(10, max(1, fps_int))

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video_url", "video_url": {"url": url, "fps": fps_int}},
                {"type": "text", "text": str(prompt_template or VIDEO_ANALYSIS_PROMPT)},
            ],
        }
    ]

    try:
        client = Ark(base_url=ark_base_url, api_key=ark_api_key)
        resp = client.chat.completions.create(
            model=ark_model_id,
            messages=messages,
            max_tokens=4096,
            temperature=0.1,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = resp.choices[0].message.content
        out = content.strip() if isinstance(content, str) else ""
        if not out:
            return None, "模型返回为空"
        return out, None
    except ArkBadRequestError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 请求错误 recording_id={recording_id}: {msg}")
        return None, f"视频生成 prompt 请求错误: {msg}"
    except ArkAPIError as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 服务错误 recording_id={recording_id}: {msg}")
        return None, "视频生成 prompt 服务暂不可用"
    except Exception as e:
        msg = str(e)
        logger.warning(f"视频生成 prompt 未知错误 recording_id={recording_id}: {type(e).__name__}: {msg}")
        return None, f"视频生成 prompt 未知错误: {type(e).__name__}: {msg}"


def video_to_prompt(
    *,
    video_url: Optional[str] = None,
    video_path: Optional[str] = None,
    video_path_mode: str = "file",
    video_base64: Optional[str] = None,
    video_file_id: Optional[str] = None,
    recording_id: Optional[str] = None,
    fps: int = 2,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> str:
    prompt, err, _, _ = generate_prompt_from_video(
        video_url=video_url,
        video_path=video_path,
        video_path_mode=video_path_mode,
        video_base64=video_base64,
        video_file_id=video_file_id,
        recording_id=recording_id,
        fps=fps,
        prompt_template=prompt_template,
    )
    if prompt:
        return prompt
    raise RuntimeError(err or "视频生成 prompt 失败")


def video_to_prompt_result(
    *,
    video_url: Optional[str] = None,
    video_path: Optional[str] = None,
    video_path_mode: str = "file",
    video_base64: Optional[str] = None,
    video_file_id: Optional[str] = None,
    recording_id: Optional[str] = None,
    fps: int = 2,
    prompt_template: str = VIDEO_ANALYSIS_PROMPT,
) -> dict:
    prompt, err, rid, fid = generate_prompt_from_video(
        video_url=video_url,
        video_path=video_path,
        video_path_mode=video_path_mode,
        video_base64=video_base64,
        video_file_id=video_file_id,
        recording_id=recording_id,
        fps=fps,
        prompt_template=prompt_template,
    )
    out: dict = {
        "ok": bool(prompt),
        "prompt": prompt or "",
        "error_message": err or "",
        "video_url": (video_url or "").strip(),
        "video_path": (video_path or "").strip(),
        "video_file_id": (fid or "").strip(),
        "recording_id": rid,
        "fps": int(fps) if isinstance(fps, int) else 2,
    }
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_video_prompt", add_help=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video-url", help="公网可访问视频 URL（http/https）")
    group.add_argument("--video-path", help="本地视频文件路径")
    group.add_argument("--video-file-id", help="Files API 上传后的 file_id（直接复用）")
    parser.add_argument(
        "--video-path-mode",
        default="file",
        choices=["file", "base64"],
        help="video-path 的模式：file=上传视频文件；base64=读取视频文件并转为 base64(data URL) 后上传",
    )
    parser.add_argument("--recording-id", default="demo", help="可选：录制会话ID")
    parser.add_argument("--fps", default="2", help="抽帧 FPS，默认 2")
    return parser


def _parse_fps(raw: str) -> int:
    try:
        return int(float(raw))
    except Exception:
        return 2


def _video_kwargs_from_args(args: argparse.Namespace) -> dict:
    if args.video_url:
        return {"video_url": args.video_url}
    if args.video_file_id:
        return {"video_file_id": args.video_file_id}
    return {"video_path": args.video_path, "video_path_mode": args.video_path_mode}


def _parse_cli() -> Tuple[argparse.Namespace, int, dict]:
    args = _build_parser().parse_args()
    fps = _parse_fps(args.fps)
    video_kwargs = _video_kwargs_from_args(args)
    return args, fps, video_kwargs


def _get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]
