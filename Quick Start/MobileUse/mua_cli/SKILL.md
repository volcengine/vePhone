---
name: mobile-use-agent
description: Run AI agent tasks on a Volcengine (火山引擎) cloud phone via the Mobile Use Agent OpenAPI. Use when the user asks to drive, automate, operate, or test an Android app on a cloud phone for enterprise use cases (e.g. reply to WeCom customer messages, add leads in a CRM, clock in on DingTalk, check invoicing stats, query inventory in a supply-chain app, ship e-commerce orders, approve OA requests) or personal ones (open 小红书 and search, place an order, check nearby places on a map), or to check status, fetch result, cancel, or list a Mobile Use run. Requires one-time setup to store Volcengine AK/SK locally; ProductId and PodId can be saved as a default device during setup, the user prompt is provided per run. Supports optional GPS injection (GpsInfo) with user consent (auto-asked only for location-related tasks).
license: MIT
agent_created: true
metadata:
  author: chenjie1129
  version: "1.0.0"
---

# Mobile Use Agent - 火山引擎云手机 Agent

通过火山引擎 Mobile Use Agent OpenAPI 在云手机上执行 AI Agent 任务（UI 自动化操作 Android App）。本 skill 提供 CLI 入口和完整工作流封装。

所有相对路径均以本 skill 的根目录（含 SKILL.md 的目录）为基准解析。

## 安全边界 (Safety Boundary)

- **发起/取消任务**会改变外部状态并可能产生云资源费用，仅在用户明确要求时执行。查询类操作（status/result/list/whoami）为只读，可随时执行。
- **绝不**要求用户在聊天中粘贴 AK/SK、不打印密钥、不把密钥放进命令行参数、不把密钥保存进本 skill 目录。让用户在自己可信的终端中运行交互式 `setup`（SK 输入不回显）。
- 本地配置检查只是客户端校验，不代表云手机任务真实成功。不要声称任务成功，除非有真实返回结果。

## 检查可用性

首次调用可能需要 Python 依赖；推荐先让用户运行 `./install.sh`（自动创建独立 venv 并装好依赖，不污染系统 Python）。入口优先用全局命令 `mua`（已安装时），否则 `python3 scripts/cli.py`：

```sh
mua whoami                       # 或: python3 scripts/cli.py whoami
```

- 若提示"未配置凭证"，请用户在自己的终端运行 `mua setup` 完成一次性配置（AK/SK 保存到 `~/.mobile_use_agent/credentials.json`，权限 600；可同时保存默认手机）。
- 若用户表示**尚未开通 Mobile Use Agent 服务 / 没有云手机资源**（或问"ProductId/PodId 在哪找"），引导其查看 README「二、开始之前：一次性准备」——按官方四步指引依次完成：给云手机开权限（ServiceRoleForIPaaS + PaasServiceRole）→ 开通服务 → 创建业务（得 ProductId）→ 订购云手机资源（得 PodId）→ 创建密钥（得 AK/SK）。已开通过的用户无需此步骤。
- 若任务目标是**云手机未预装的应用**（默认镜像只预装少量 App），先引导用户在 [MUA 控制台「发布 App」](https://www.volcengine.com/docs/6394/1223958?lang=zh) 安装到云手机，再执行任务。
- 若任务执行中遇到**人脸识别验证**（如登录银行/支付类 App），引导用户用手机扫码完成验证（官方流程见 README「五、常见问题」）：云手机画面弹出二维码（或点"H5 扫码链接"）→ 手机扫码 → 手机端完成登录与人脸扫描 → 回控制台点"重新连接"。扫码期间云手机画面提示"连接异常"是正常现象。
- 若依赖缺失，优先让用户运行 `./install.sh`（建独立环境），避免往系统 Python 装包。

## 执行用户请求的任务

默认走最便捷的 `RunAgentTaskOneStep`（免预创建配置），自动轮询步骤并实时增量打印，最后拉取最终结果：

```sh
mua run --product-id PID --pod-id POD --prompt "打开企业微信，回复最新客户消息"
```

- **用户提示词每次提供**；**ProductId/PodId 优先用 setup 时保存的默认手机**（命令行参数可覆盖）。缺少时交互式向导补齐。
- 任务执行中步骤会增量打印（`-- Step N [OK]`），结束后展示状态/内容/截屏 URL/用量；失败时自动归因（打印中文失败原因、操作建议、错误码）。
- 轮询/取消/续跑/录屏/输出 schema 等高级用法见 [references/commands.md](references/commands.md)。

### GPS 定位注入（可选）

云手机无 GPS 硬件，可通过 `GpsInfo` 注入虚拟定位（地图类 App 显示指定位置）。**仅当任务涉及位置时**（提示词含 附近/地图/导航/外卖/打车 等词）程序会自动询问用户是否允许获取本机位置；无关任务不打扰：

```sh
# 交互式：位置相关任务会询问"是否允许获取当前位置"（拒绝则不注入，功能不受影响）
mua run --product-id PID --pod-id POD --prompt "打开地图查看附近美食"

# 非交互/已授权：--gps 显式允许并注入
mua run --product-id PID --pod-id POD --prompt "打开地图" --gps --no-interactive
```

定位获取为**多来源统一接口 + 自动降级链**（按精度从高到低）：文本/分享链接坐标解析 → 图片 EXIF → macOS CoreLocation（米级，需授权）→ IP 定位（城市级）→ 地名地理编码 → 手动输入兜底。仅 `system` 来源需要系统授权，拒绝授权时仍可走解析/手动输入。坐标系统一 WGS-84。获取结果会告知用户（来源/坐标/精度）。详见 [references/gps.md](references/gps.md)。

## 只读查询

```sh
mua status --run-id RUN_XXX   # 查询任务当前步骤
mua result --run-id RUN_XXX   # 获取任务运行结果
mua list                      # 查询任务列表
mua whoami / mua device       # 凭证与默认手机状态
```

## 错误处理

所有 API 错误统一转为 `MobileUseError`（错误码 + 中文描述 + 操作建议 + 分类）。认证类错误提示用户重新 `setup`；资源类错误提示检查 ProductId/PodId；`ErrAssumeRoleFailed` 提示完成跨服务授权——[授权 ServiceRoleForIPaaS](https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas) 并创建 `PaasServiceRole` 角色（详见 README「二、开始之前」第 1 步）。完整错误码表和双通道捕获说明见 [references/error_codes.md](references/error_codes.md)。

## 编程式调用

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from mobile_use_agent import MobileUseAgentClient
from credential_store import load_credentials

ak, sk = load_credentials()                       # 复用本地凭证
client = MobileUseAgentClient(ak=ak, sk=sk)
result = client.run_and_wait(
    run_name="my-task", pod_id="POD", product_id="PID",
    user_prompt="打开企业微信查看未读消息", gps_info=None,   # 每次动态传入
)
```

更多示例见 [scripts/examples.py](scripts/examples.py)。
