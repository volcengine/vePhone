# UI Test Demo（Mobile Use / Cloud Phone）

这是一个“用例驱动”的 UI 自动化执行器示例：

- 从 `cases/` 目录读取 Markdown（`*.md`）或 `*.case` 用例文本。
- 调用云端 Mobile Use / Cloud Phone 能力执行用例（`RunAgentTaskOneStep` / `RunAgentTask`）。
- 任务执行后轮询 `ListAgentRunCurrentStep` 获取当前步骤，出现 `finished` / `request_user` 即认为任务进入收敛阶段。
- 任务进入收敛阶段后调用 `GetAgentResult` 获取最终运行结果，并生成结构化的 `pass/fail/skip`。
- 支持按 `POD_ID_LIST` 串行/并行执行。
- 运行过程中**增量落盘**到 `results/*.jsonl`（一行一条用例结果），运行结束后生成最终 `results/*.json`（JSON 数组）。
- 对于超时 / 异常 / Ctrl+C 中断，会尽力调用 `CancelTask` 取消远端任务，并把取消结果摘要写入结果 JSON（`cancel_ok/cancel_error_message/cancel_task`）。
- 提供本地页面 `results.html` 用于结果汇总、筛查、排序与详情查看。

> 如需查看接口原始响应，请使用 `validate-env/query/cancel` 命令查看输出。用例结果文件 `results/*.json`/`results/*.jsonl` 不包含 `ResponseMetadata`。

---
## 0. 目录结构与文件含义

### 0.1 目录结构

当前 `ui_test_demo/` 目录结构如下（省略 `.venv/`、`__pycache__/`、`.pytest_cache/` 等运行时生成内容）：

```text
ui_test_demo/
├── .env
├── .env.example
├── .gitignore
├── README.md
├── cases/
│   └── template.md
├── results/
│   ├── YYYYmmdd_HHMMSS.jsonl
│   ├── YYYYmmdd_HHMMSS.json
│   └── sample.json
├── results.html
├── pyproject.toml
├── requirements.txt
├── uv.lock
└── src/
    ├── __init__.py
    ├── app_runner.py
    ├── case_runner.py
    ├── env_utils.py
    ├── main.py
    ├── mobile_use.py
    └── system_prompt.py
```

### 0.2 文件/目录含义

- `src/main.py`
  - 程序入口，调用 `src/app_runner.py::run_cli()`。
  - 对应命令：`uv run python -m src.main ...`

- `src/app_runner.py`
  - CLI 与整体编排层：
    - `run`：执行用例、增量落盘、最终汇总
    - `validate-env`：用 `DetailPod` 校验环境变量（PRODUCT_ID/POD_ID_LIST 等）
    - `query`：查询 `GetAgentResult` + `ListAgentRunCurrentStep`
    - `cancel`：调用 `CancelTask`
    - `progress`：读取 `results/*.jsonl` 计算 done/total
  - 负责生成 `results/*.jsonl` 与最终 `results/*.json`。

- `src/case_runner.py`
  - 用例执行核心：
    - 发现 `cases/` 中用例文件
    - 拼装 prompt + case 文本并触发执行（`RunAgentTaskOneStep/RunAgentTask`）
    - 轮询 `ListAgentRunCurrentStep`，以 `finished/request_user` 作为结束信号
    - 拉取 `GetAgentResult`，解析 `IsSuccess` 枚举映射 `pass/fail/skip`
    - 处理超时/异常/中断，best-effort `CancelTask`

- `src/mobile_use.py`
  - OpenAPI/SDK 调用封装层（UniversalApi）：
    - `RunAgentTaskOneStep` / `RunAgentTask`
    - `ListAgentRunCurrentStep`
    - `GetAgentResult`
    - `CancelTask`
    - `DetailPod`（仅使用该接口获取 Pod 镜像/AOSP 信息）
  - 同时包含 `GetAgentResult` 返回解析与结果对象构建逻辑（截图/Token/Pod 信息等）。

- `src/env_utils.py`
  - `.env` 加载与布尔环境变量解析（例如 `env_bool`）。

- `src/system_prompt.py`
  - 系统提示词（SYSTEM_PROMPT）：规定 Agent 如何执行用例、如何输出结构化 JSON（`StructOutput`）。

- `cases/`
  - 用例目录：每个文件代表一个测试用例（Markdown 或纯文本）。
  - `template.md` 是模板示例，执行器会跳过模板类文件（不作为真实用例执行）。

- `results/`
  - 运行输出目录：
    - `YYYYmmdd_HHMMSS.jsonl`：增量落盘（一行一条结果；第一行是 `__meta__`）
    - `YYYYmmdd_HHMMSS.json`：本次 run 的最终汇总（JSON 数组）
    - `sample.json`：示例数据，用于 `results.html` 的“加载示例”

- `results.html`
  - 本地结果浏览页面：
    - 加载 `results/*.json` 展示汇总/图表/表格
    - 支持查看 `content/struct_output`（弹窗）与排序
    - 支持展示 `run_id/pod_id/task_status/cancel_*` 等诊断字段

- `.env` / `.env.example`
  - `.env`：你的本地私密配置（AK/SK、PodId 等）
  - `.env.example`：配置模板（可复制成 `.env`）

- `pyproject.toml` / `uv.lock`
  - `uv` 依赖与锁定文件，推荐使用 `uv sync` 安装依赖。

- `requirements.txt`
  - 兼容 `pip` 的依赖列表（如果不使用 `uv`，可以用 `pip install -r requirements.txt`）。

---

## 1. 环境准备

### 1.1 Python & uv

推荐 Python 3.12（仓库包含 `.python-version`）。

在 `ui_test_demo/` 目录下执行：

```bash
uv venv --python 3.12
```

```bash
uv sync --dev
```

### 1.2 配置 .env

复制示例：

```bash
cp .env.example .env
```

程序启动时会从项目根目录自动加载 `.env`（`src/env_utils.py::load_env_from_root`），默认**不覆盖**系统环境变量中已存在的同名 key。

---

## 2. 环境变量说明

`.env.example` 中包含基础变量，这里按用途分类说明。

### 2.1 云账号与服务端配置（必填）

本节列出的所有环境变量**均为必填**（缺少任意一项都会导致接口调用失败或无法正确执行用例）。请先完整配置 `.env` 再执行任务。

- `VOLC_ACCESSKEY` / `VOLC_SECRETKEY`  
  火山引擎统一 AK/SK。账号需要针对Mobile Use / Cloud Phone **需要完成服务授权**。
  - 授权链接：https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas

- `VOLC_HOST`  
  Universal API 访问域名，例如：`open.volcengineapi.com`

- `PRODUCT_ID`  
  Mobile Use / Cloud Phone 产品 ID。

- `POD_ID_LIST`  
  PodId 列表，逗号分隔，例如：`1234567890,1234567891`

- `TOS_BUCKET` / `TOS_ENDPOINT` / `TOS_REGION`  
  用于截图等资源回传的 TOS 配置。
  - `TOS_BUCKET`：TOS 存储桶名称，例如：`mobile-use-demo`
  - `TOS_ENDPOINT`：TOS 访问域名，例如：`tos-cn-beijing.volces.com`
  - `TOS_REGION`：TOS 区域，例如：`cn-beijing`

### 2.2 执行器配置（可选）

未设置时使用代码默认值。

- `CASE_FILTER`：用例过滤关键字（逗号分隔）
  - 以用例**相对路径**为匹配对象
  - 例如：`CASE_FILTER=douyin,draft` 会执行路径中包含 `douyin` 或 `draft` 的用例

- `CASE_TIMEOUT_S`：单用例最大等待时间（秒），默认 `600`

- `POLL_INTERVAL_S`：轮询间隔（秒），默认 `2`

- `PROGRESS_LOG_EVERY`：进度日志输出频率
  - 默认 `1`，即每完成 1 个用例输出一条 `PROGRESS ...`
  - 设置为 `5` 则每 5 个用例输出一次进度

### 2.3 视频转 Prompt（可选）

当你有一段操作录屏希望生成“可复刻的步骤提示词”，仓库提供了一个独立的 CLI（不会影响 `run` 的用例执行逻辑）：

- 代码位置：`src/video_prompt/`
- 依赖：`volcengine-python-sdk[ark]`
- 环境变量（见 `.env.example`）：
  - `ARK_BASE_URL` / `ARK_API_KEY` / `ARK_MODEL_ID`
- 视频限制：参考 https://www.volcengine.com/docs/82379/1895586?lang=zh#8e3a48ed
  - 使用 `--video-path-mode file` 直接上传视频文件时，需要模型拥有 Response API 权限

支持参数（`uv run python -m src.video_prompt.run_video_prompt -h`）：
- `--video-url <URL>`：公网可访问视频 URL（http/https）。必填（三选一）
- `--video-path <PATH>`：本地视频文件路径。必填（三选一）
- `--video-file-id <FILE_ID>`：已通过 Files API 上传得到的 `file_id`（直接复用）。必填（三选一）
- `--video-path-mode {file,base64}`：仅在 `--video-path` 时生效，默认 `file`。选填
  - `file`：直接上传视频文件
  - `base64`：读取视频文件并转为 base64(data URL) 后上传
- `--recording-id <ID>`：录制会话 ID，默认 `demo`。选填
- `--fps <N>`：抽帧 FPS，默认 `2`。选填

调用示例（只包含必填参数；在 `ui_test_demo/` 目录下）：

- 通过 `--video-url` 上传公网视频 URL：
```bash
uv run python -m src.video_prompt.run_video_prompt --video-url "https://YOUR_TOS_URL"
```
- 通过 `--video-path` 上传本地视频文件（默认 `file` 模式）：
```bash
uv run python -m src.video_prompt.run_video_prompt --video-path "/abs/path/to/video.mp4"
```
- 通过 `--video-path` 上传本地视频文件（`base64` 模式）：
```bash
uv run python -m src.video_prompt.run_video_prompt --video-path "/abs/path/to/video.mp4" --video-path-mode base64
```
- 通过 `--video-file-id` 复用已上传视频文件：
```bash
uv run python -m src.video_prompt.run_video_prompt --video-file-id "file_xxx"
```

---

## 3. 命令行用法（CLI）

所有命令都通过模块入口调用：

```bash
uv run python -m src.main <subcommand> [args...]
```

其中 `src/main.py` 会转发到 `src/app_runner.py::run_cli()`。

---

## 4. 执行用例：`run`（默认）

```bash
uv run python -m src.main run
```

或省略子命令（等价 `run`）：

```bash
uv run python -m src.main
```

该子命令会执行 `cases/` 目录下的用例（受 `CASE_FILTER` 过滤影响）。

### 4.1 执行前环境校验（强制）

`run` 会在执行用例前做一次**环境有效性校验**（失败会直接退出，不执行任何用例）：

- 对 `POD_ID_LIST` 中每个 `PodId` 调用一次 `DetailPod`（`MobileUseClient.detail_pod_raw`），校验：
  - 响应顶层 `Error` 不存在
  - `PRODUCT_ID` 不为空
  - 返回 payload 支持两种结构（兼容两种返回格式）：
    1) `{"Result": {...}}`
    2) `{...}`（payload 直接在顶层）
  - 若 payload 中包含 `product_id/pod_id`（或 `ProductId/PodId`）字段，则必须与请求一致
  - 若 payload 中包含 `image_id/ImageId` 字段，则不允许为空

校验失败会 `SystemExit(2)`（退出码 2）。

单独运行校验：

```bash
uv run python -m src.main validate-env --pretty
```

### 4.2 用例过滤：`CASE_FILTER`

执行特定用例（例如文件名包含 `douyin-draft-create`）：

```bash
CASE_FILTER=douyin-draft-create uv run python -m src.main run
```

### 4.3 运行时进度日志：`PROGRESS_LOG_EVERY`

`case_runner.run_suite()` 会在用例结束时输出 `PROGRESS ...` 进度日志：

示例（日志）：
`PROGRESS 3/20 (15%) pass=2 fail=1 skip=0 last=cases/douyin-draft-create.md status=fail`

修改频率：

```bash
PROGRESS_LOG_EVERY=5 uv run python -m src.main run
```

---

## 5. 环境校验：`validate-env`

```bash
uv run python -m src.main validate-env --pretty
```

可选参数：

- `--pod-id <POD_ID>`：只校验一个指定 PodId（否则使用环境变量中的 `POD_ID_LIST`）

输出结构：

```json
{
  "ok": true,
  "error_message": "",
  "DetailPod": {
    "<pod_id_1>": { "...": "..." },
    "<pod_id_2>": { "...": "..." }
  }
}
```

---

## 6. 进度查询：`progress`

执行 `run` 后会生成 JSONL 文件，例如：

- `results/20260107_095942.jsonl`

`progress` 会通过读取 JSONL 的：

- 第一行 `__meta__`（包含 `total_cases` 等）
- 当前已写入的结果行数（done）

来计算 `done/total`。

### 6.1 默认查看最新 JSONL

```bash
uv run python -m src.main progress --pretty
```

### 6.2 持续刷新（watch）

```bash
uv run python -m src.main progress --watch --interval 1 --pretty
```

### 6.3 指定某次运行的 JSONL

```bash
uv run python -m src.main progress --jsonl results/20260107_095942.jsonl --pretty
```

---

## 7. RunId 诊断：`query` / `cancel`

### 7.1 查询：`query`

默认同时查询：
- 运行结果：`GetAgentResult`
- 当前步骤：`ListAgentRunCurrentStep`

```bash
uv run python -m src.main query <RUN_ID> --pretty
```

可选参数：

- `--no-detail`：`GetAgentResult` 使用 `IsDetail=false`
- `--result-only`：只调用 `GetAgentResult`
- `--step-only`：只调用 `ListAgentRunCurrentStep`

示例：

```bash
uv run python -m src.main query <RUN_ID> --result-only --pretty
```

```bash
uv run python -m src.main query <RUN_ID> --step-only --pretty
```

### 7.2 取消：`cancel`

```bash
uv run python -m src.main cancel <RUN_ID> --pretty
```

> `cancel` 输出为接口原始响应（可能包含服务端自带的元信息），用于诊断与排查；用例结果文件 `results/*.json`/`results/*.jsonl` 不包含 `ResponseMetadata`。

---

## 8. 用例目录：`cases/`

- 所有用例位于 `cases/` 目录
- 支持：
  - Markdown：`*.md`
  - 文本：`*.case`
- 默认规则：
  - 忽略隐藏文件（以 `.` 开头）
  - 忽略 `template.*` 模板用例
- 用例内容为空时，该用例会被标记为 `skip`，结果中 `reason` 为 `"用例内容为空"`。

---

## 9. 任务轮询与结束判定（重要）

### 9.1 轮询链路

单条用例的执行过程：

1) 调用 `RunAgentTaskOneStep` / `RunAgentTask` 获取 `RunId`  
2) 轮询 `ListAgentRunCurrentStep`  
3) 当满足“结束信号”后，调用 `GetAgentResult` 获取最终结果  
4) 根据 `GetAgentResult.IsSuccess` 枚举映射为 `pass/fail/skip`，并提取截图/用量等信息落盘

### 9.2 结束信号（ListAgentRunCurrentStep）

当 `ListAgentRunCurrentStep` 返回中满足任一条件，即进入“拉取最终结果”阶段：

- `Results[*].Action == "finished"`
- `Results[*].Action == "request_user"`
- 或返回内容任意位置出现 `request_user`（常见于 `Param/content/StepResult.Result` 等）

### 9.3 最终状态（GetAgentResult.IsSuccess）

`IsSuccess` 为枚举值，当前执行器按以下规则解释：

- `0`：NOT_COMPLETED（未完成；继续等待，不应作为终态）
- `1`：SUCCESS → `pass`
- `2`：EXEC_FAILED → `fail`
- `3`：COMPLETED_BUT_NO_MESSAGE → `pass`
- `4`：USER_INTERRUPT → `fail`
- `5`：USER_CANCELLED → `skip`
- `6`：UNKNOWN_ERROR → `fail`

---

## 10. 结果文件：JSONL + JSON

### 10.1 增量文件：`results/<timestamp>.jsonl`

执行 `run` 时，会创建 JSONL，例如：

- `results/20260107_095942.jsonl`

写入逻辑：

1. 第一行写入 meta：

```json
{"__meta__":{"created_at":"2026-01-07T09:59:42Z","total_cases":10,"cases_dir":".../cases","exec_mode":"auto"}}
```

2. 每当一个用例结束（pass/fail/skip），追加一行该用例结果（一个 JSON 对象）。

### 10.2 最终结果：`results/<timestamp>.json`

执行完成后，从 JSONL 读回所有结果行，按用例顺序排序，写入最终 JSON 数组：

- `results/20260107_095942.json`

`results.html` 读取的是该 `.json` 文件（不是 `.jsonl`）。

---

## 11. 单条用例结果字段说明

结果由 `src/mobile_use.py::ResultItem` 与 `src/case_runner.py` 共同组装。

### 11.1 基础字段（总会存在）

- `case`：用例相对路径，例如 `cases/douyin-draft-create.md`
- `status`：`pass` / `fail` / `skip`
- `timestamp`：北京时间字符串（`YYYY-MM-DD HH:MM:SS`）
- `duration_ms`：执行耗时（毫秒）
- `reason`：失败或跳过原因；通过时通常为空字符串

### 11.2 任务标识与轮询信号（可选）

- `run_id`：本次执行的 RunId（用于 `query/cancel`）
- `pod_id`：执行该用例的 PodId
- `task_status`：由 `ListAgentRunCurrentStep` 提取的结束信号（`finished` 或 `request_user`），用于诊断

### 11.3 资源与用量（可选）

- `screenshot`：截图 URL 数组（从 `GetAgentResult.Result.ScreenShots` 或顶层 payload 中提取）
- `original_dimensions`：截图原始尺寸 `[width, height]`（仅记录第一张）
- `screenshot_dimensions`：缩放后截图尺寸 `[width, height]`（仅记录第一张）
- `in_tokens` / `out_tokens`：Token 用量（若服务端返回 `Usage.in_tokens/out_tokens`）

### 11.4 Pod / 镜像信息（可选）

通过 `MobileUseClient._get_pod_image_info()` 调用 `DetailPod` 查询：

- `AospVersion`：Android/AOSP 版本
- `ImageName`：镜像名称
- `ImageId`：镜像 ID

### 11.5 取消信息（可选）

当本地超时/中断/异常触发 `CancelTask` 时：

- `cancel_ok`：是否认为 CancelTask 触发成功（基于 CancelTask 返回中 `Result` 是否存在且非空）
- `cancel_error_message`：取消失败/不确定时的错误信息（例如返回缺少 `Result` 或 `Result` 为空）
- `cancel_task`：取消接口返回的 `Result`（若可用）

### 11.6 详情字段（可选）

- `content`：`GetAgentResult` 返回的 `Content`（原始文本）
- `struct_output`：`GetAgentResult` 返回的 `StructOutput`（结构化输出，可能为 dict 或字符串）

执行器也会尝试从 `content/struct_output` 推断最终 `status/reason`（当 SDK 认为成功但用例自检认为失败/跳过时，以用例为准）。

---

## 12. 结果页面：`results.html`

### 12.1 使用方式

- 推荐直接双击打开 `results.html`，然后：
  - 选择 `results/` 目录（左侧“目录选择”）并在列表里选择 `.json` 文件加载
  - 或者用“文件选择”直接选择某个 `results/*.json` 加载

如果你希望 `加载示例` 里自动 `fetch('results/sample.json')` 生效（某些浏览器在 `file://` 下会限制 fetch），可使用本地静态服务启动：

```bash
cd ui_test_demo && python -m http.server 8000
```

然后打开：`http://localhost:8000/results.html`

### 12.2 页面支持

- 汇总：总数/通过/失败/跳过
- 图表：状态分布、失败原因分布、耗时直方图
- 表格排序：点击表头排序
- 详情查看：点击 `content` 单元格打开弹窗，查看/复制完整 `content` 与 `struct_output`
- 新增展示字段：`run_id/pod_id/task_status/cancel_ok/cancel_error_message`

---
