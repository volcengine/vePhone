# Mobile Use Agent（云手机 AI 助手）

让 AI 帮你操作一台"云端的安卓手机"：打开 App、搜索、下单、看地图……你说一句话，AI 在云手机里自动完成。不用自己装 App、不用盯屏幕，任务跑完把结果带给你。

> **这是给 AI 助手的"一只手"**：一份通用技能包（Skill）。装进任何支持技能的 AI 助手，或接入你自己的 AI Agent，它就能多一只手，远程操作云端的安卓手机。
>
> **只动云端，不碰本机**：被操作的是火山引擎的一台云手机，全程在云端执行——**你的电脑、你自己的手机都不会被读取或触碰**，任务跑完把结果带回来。

面向三类读者，各取所需：

| 你是谁 | 看哪节 |
|---|---|
| 不想碰命令行，只想让 AI 帮干活 | [三、用起来 · 方式 A](#三用起来--方式-a推荐让-ai-直接帮你做) |
| 愿意敲几行命令 | [四、用起来 · 方式 B](#四用起来--方式-b命令行三步) |
| 有自己的 AI Agent，想接云手机能力 | [七、集成到你的 AI Agent](#七集成到你的-ai-agent开发者) |

> 无论哪种方式，都需要先完成 [二、开始之前的一次性准备](#二开始之前一次性准备约-10-分钟)。

---

## 一、这是什么？

Mobile Use Agent（简称 MUA）是火山引擎云手机上的一个 AI 助手。它像人一样"看着"云手机屏幕、点按、滑动、输入，帮你完成真实手机上的操作。

可以做的事（企业应用示例，覆盖不同业务职能线）：

- **客户沟通**：`打开企业微信，把最新一条客户消息回复"收到，今天下班前给您反馈"`
- **销售管理**：`打开 CRM 系统，新增客户「华信科技」，联系人张经理，电话 13800138000`
- **供应链**：`打开进销存系统，查询 A4 纸的当前库存，少于 100 箱就提醒我补货`
- **流程审批**：`打开 OA 系统，把待审批的请假申请都通过掉`

财务开票、电商订单发货、考勤打卡、数据查询……企业里跑在手机上的业务，它都能照做。

生活场景（查天气、找餐厅、刷短视频……）同样能做——你只管说，它照做。

**它和你自己的手机是什么关系？** 无关。它操作的是火山引擎给你提供的一台"云手机"——一台 24 小时在云端运行的真实安卓手机。你的电脑不需要装任何手机 App，任务在云端执行，你在本地看结果。它在云端的安卓系统里活动，和你的本地设备是两个世界——不会读取、操作你电脑或手机上的任何东西。

---

## 二、开始之前：一次性准备（约 10 分钟）

要用云手机，需要先在火山引擎开通服务并准备好"手机"和"钥匙"。**只需做一次**，之后一直可用。以下流程按官方文档 [正式接入 MUA](https://docs.volcengine.com/docs/6394/2603614?lang=zh) 整理。

> 若已开通过、已有云手机资源，可跳过本节，直接看 [三、用起来](#三用起来--方式-a推荐让-ai-直接帮你做)。

### 第 1 步 给云手机开权限（约 2 分钟）

云手机执行任务时需要访问你的其他云资源（比如保存截图的对象存储）。这一步是**授权**，不做后面会报错。

1. 打开 [ServiceRoleForIPaaS 授权页](https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas)，点 **"立即授权"**；
2. 打开 [角色管理](https://console.volcengine.com/iam/identitymanage/role/)，点 **"新建角色"**：
   - 信任身份选 **"服务"** → 服务选 **"云手机"** → 下一步；
   - 角色名填 **`PaasServiceRole`**（复制这个拼写）→ 下一步；
   - 勾选全部策略，作用范围选"全局"，提交。

> 💡 若页面提示"已授权"或角色已存在，跳过即可。

### 第 2 步 开通 Mobile Use Agent 服务（约 1 分钟）

1. 打开 [云手机控制台](https://console.volcengine.com/ACEP/Business/6)，点页面上的 **"立即开通"**；
2. 弹窗中确认计费项，勾选同意条款和服务协议，点 **"立即开通"**。

### 第 3 步 创建"业务"，拿到 ProductId（约 1 分钟）

"业务"是云手机服务的组织单元，**ProductId 就是它的业务 ID**：

1. 打开 [MUA 控制台](https://console.volcengine.com/ACEP/mua/)；
2. 若还没有业务，系统会自动弹出新建框；填个名字（如 `my-phone`），点确定；
3. 在**业务管理页**看到的一串 ID，就是 `ProductId`。

### 第 4 步 订购云手机，拿到 PodId（约 5 分钟，含等待）

云手机资源就是那台"云端的手机"，**PodId 是这台手机的实例 ID**：

1. 在 [MUA 控制台](https://console.volcengine.com/ACEP/mua/) 左侧点 **"+ 新任务"**；
2. 对话框左下角点 **"+ 订购云手机"**，按提示选地域、规格（推荐 8vCPU｜24GB｜256GB）、数量，下单；
3. 首次订购约 **2～3 分钟**开通，之后到「**云手机资源**」页面看到实例 ID，就是 `PodId`；
4. ⚠️ 实例状态需为"**运行中**"才能执行任务。

> 📎 相关官方文档：[创建 MUA 业务](https://docs.volcengine.com/docs/6394/2298713) · [创建云手机资源](https://docs.volcengine.com/docs/6394/2604742) · [使用 MUA 执行任务](https://docs.volcengine.com/docs/6394/2298710)

### 第 5 步 创建密钥，拿到 AK/SK（约 1 分钟）

密钥是"钥匙"，本工具用它证明"是你"在调用云手机：

1. 打开 [访问密钥管理](https://console.volcengine.com/iam/keymanage)；
2. 点 **"新建密钥"**，创建后得到一对 **AK**（AccessKey ID）和 **SK**（Secret Access Key）。

### 你需要在手边的 4 个值

| 值 | 哪一步拿到 | 一句话说明 |
|---|---|---|
| `ProductId` | 第 3 步 | 业务的 ID |
| `PodId` | 第 4 步 | 那台云手机的 ID |
| `AK` / `SK` | 第 5 步 | 你的"钥匙"，请妥善保管 |

---

## 三、用起来 · 方式 A（推荐：让 AI 直接帮你做）

如果你在用支持技能（Skill）的 AI 助手（不限于任何品牌），**不需要敲任何命令**——直接把任务告诉 AI 即可：

```
你：帮我在云手机上打开企业微信，把最新一条客户消息回复"收到，今天下班前给您反馈"
```

AI 会：

1. 检测到你的云手机凭证尚未配置 → 引导你在终端运行一次 `mua setup`（只需一次）；
2. 之后每次你只需描述任务，AI 自动调用云手机执行并回报结果。

**这是最省事的用法**：你只负责"说"，AI 负责"做"。

---

## 四、用起来 · 方式 B（命令行三步）

适合愿意用终端、想自己控制的人。

### 第 1 步 安装（一次性）

```bash
./install.sh        # 创建独立环境 + 提供全局命令 mua
```

安装脚本会做两件事：**① 创建一个独立的 Python 环境并装好全部依赖**（放在 `~/.local/share/mobile-use-agent/venv`，不影响你电脑上已有的任何 Python）；**② 把 `mua` 命令装到 `~/.local/bin`**。整个过程不需要你懂 Python，也不需要提前装任何东西（只要系统有 Python 3）。

> ⚡ **首次安装约 1 分钟**：依赖里的火山引擎官方 SDK 是 137 个产品的"全家桶"（完整安装约 9 分钟），但本工具只用其中 1 个模块，安装脚本会**只抽取用到的部分**（2.6 万个文件 → 55 个），运行行为与完整安装完全一致；万一精简安装失败，会自动回退到官方完整安装，无需手动处理。之后再次运行 `./install.sh` 会秒过（环境已存在则直接复用）。

安装后任意目录都能用 `mua`。

### 第 2 步 配置（一次性）

```bash
mua setup
```

输入第 5 步拿到的 AK/SK（SK 输入时屏幕不显示，属正常）；程序会问是否保存"默认手机"，输入第 3/4 步的 ProductId/PodId 即可——之后就不用再填了。

### 第 3 步 运行任务

```bash
mua run
```

然后按提示描述任务即可：

```
请描述任务: 打开企业微信，查看未读消息，把最新一条回复：收到，今天下班前给您反馈
[手机] 使用默认云手机: ProductId=prod-1f3a****d5a6  PodId=pod-87****4321
-- Step 1 [OK] --
   [action] finished
   [content] 已打开企业微信, 并回复了最新一条客户消息。
[任务结束] 状态: 成功
```

之后每次只需 `mua run`，描述新任务即可。

> **新手小贴士**
>
> - 不知道让它做什么？在"请描述任务"处输入序号（如 `1`），直接用现成示例：**企业应用场景**（企业微信回客户消息、CRM 录入客户、钉钉考勤打卡、开票统计、进销存查库存、电商后台发货、OA 审批）覆盖不同业务职能线，直观展示"AI 替你干活"；**生活场景**（看桌面、发微信、刷抖音、找餐厅、查天气）让新手快速上手。带 `*` 的示例需要云手机上已安装对应 App。
> - 第一次运行会先显示欢迎页，告诉你需要准备的 4 个值去哪找、怎么配。
> - 报错了别慌——程序会用大白话告诉你"发生了什么、你该怎么办"，照着做就行。
> - 任务跑完会明确告诉你"完成 / 未完成"和用时，结果一目了然。

---

## 五、常见问题

### 云手机里没装我要用的 App？

默认云手机只预装少量应用。若任务需要特定 App（如小红书），需先在控制台"**发布 App**"安装到云手机：[发布 App 指引](https://www.volcengine.com/docs/6394/1223958?lang=zh)。装好后即可让 AI 操作它。

### 遇到人脸识别验证（如登录银行 App）？

云手机没有摄像头，但可以**用你的手机扫码完成验证**：

1. 任务执行到人脸验证环节时，控制台上云手机画面会弹出二维码（或点控制台任务右侧"**H5 扫码链接**"）；
2. 用你手机上的相机/微信扫这个码，在手机上完成登录与人脸扫描；
3. 扫脸时云手机画面提示"连接异常"是**正常现象**（手机端接管了摄像头），无需处理；
4. 完成后回到控制台点"**重新连接**"，任务继续执行。

> 📎 官方文档：[步骤四：使用手机扫码完成人脸识别验证](https://docs.volcengine.com/docs/6394/2603617)

### 任务报错怎么办？

- `ErrAssumeRoleFailed`：没做第 1 步授权，回 [第 1 步](#第-1-步-给云手机开权限约-2-分钟) 补授权；
- `InvalidAccessKey`：AK/SK 不对或过期，运行 `mua setup` 重新配置；
- 提示实例未运行：回 [第 4 步](#第-4-步-订购云手机拿到-podid约-5-分钟含等待) 确认云手机处于"运行中"。

### 找不到 ProductId / PodId？

`ProductId` 在 [MUA 控制台 → 业务管理](https://console.volcengine.com/ACEP/mua/)；`PodId` 在 [MUA 控制台 → 云手机资源](https://console.volcengine.com/ACEP/mua/)。找到后用 `mua setup` 存为默认手机，之后不用再找。

---

## 六、常用命令速查

```bash
mua setup          # 配置 AK/SK、默认手机（首次）
mua run            # 运行任务（问答式向导）
mua whoami         # 查看凭证与默认手机状态
mua device         # 查看默认手机（--clear 清除）
mua status --run-id RUN_XXX    # 查询任务进度
mua result --run-id RUN_XXX    # 获取任务结果
mua cancel --run-id RUN_XXX    # 取消任务
mua list           # 任务列表
```

完整命令与参数见 [references/commands.md](references/commands.md)。

---

## 七、集成到你的 AI Agent（开发者）

如果你**已经有一个自己的 Agent**（LangChain / LlamaIndex / 自研 function-calling / 任何 LLM 应用），想给它加上"操作真实手机"的能力，`scripts/` 就是可直接 import 的 Python 工具库。

```bash
git clone https://github.com/chenjie1129/mobile-use-agent.git
pip install -r mobile-use-agent/requirements.txt
```

```python
import sys
sys.path.insert(0, "/path/to/mobile-use-agent/scripts")   # 指向 scripts/ 目录

from mobile_use_agent import MobileUseAgentClient
from credential_store import load_profile    # {ak, sk, product_id, pod_id}
```

凭证复用 `mua setup` 已保存的本地配置（权限 600），**代码中不出现任何密钥**。

### 方式一：注册为工具（function calling，推荐）

```python
profile = load_profile()
client = MobileUseAgentClient(ak=profile["ak"], sk=profile["sk"])

# 1) 工具 schema：交给你的 LLM
MUA_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "operate_cloud_phone",
        "description": "在火山引擎云手机上执行真实手机操作（回客户消息、CRM 录入客户、开票统计、查库存、电商发货、处理审批等企业应用任务，也可搜索、下单），返回任务结果",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "自然语言描述想执行的操作，如「打开 CRM 系统新增客户华信科技」"},
                "product_id": {"type": "string", "description": "MUA 业务 ID，留空使用默认手机"},
                "pod_id": {"type": "string", "description": "云手机实例 ID，留空使用默认手机"},
            },
            "required": ["prompt"],
        },
    },
}

# 2) 工具实现：LLM 决定调用时，你的代码执行到这里
def operate_cloud_phone(prompt: str, product_id: str = "", pod_id: str = "") -> dict:
    product_id = product_id or profile["product_id"]   # 默认手机回退
    pod_id = pod_id or profile["pod_id"]
    if not product_id or not pod_id:
        raise ValueError("缺少 ProductId/PodId：先运行 `mua setup` 保存默认手机，或调用时传入")

    return client.run_and_wait(
        run_name="agent-tool-task",
        product_id=product_id,
        pod_id=pod_id,
        user_prompt=prompt,
        gps_info=None,   # 可选：位置相关任务可先征求用户同意，再调 geo.acquire_gps() 注入
    )
```

### 方式二：直接调用客户端 API（异步 / 事件驱动）

```python
resp = client.run_agent_task_one_step(
    run_name="async-task",
    product_id=profile["product_id"],
    pod_id=profile["pod_id"],
    user_prompt="打开企业微信查看未读消息",
)
run_id = resp["RunId"]                       # 立即返回，任务在云端后台执行

steps  = client.list_agent_run_current_step(run_id)   # 当前执行到哪一步
result = client.get_agent_result(run_id)              # 最终结果（含截屏/输出）
client.cancel_task(run_id)                            # 需要时取消
```

### 核心接口一览

| 客户端方法 | 对应 OpenAPI | 用途 |
|---|---|---|
| `run_agent_task_one_step` | RunAgentTaskOneStep | 启动任务（免预配置），返回 `RunId` |
| `list_agent_run_current_step` | ListAgentRunCurrentStep | 查询任务当前执行步骤 |
| `get_agent_result` | GetAgentResult | 获取最终结果 |
| `cancel_task` | CancelTask | 取消任务 |
| `list_agent_run_task` | ListAgentRunTask | 查询任务列表 |
| `run_and_wait` | 组合封装 | 启动 + 轮询 + 取结果（阻塞式） |

更多参数（GPS 注入、TOS 截图、录屏、MCP 工具、输出 Schema）见 [scripts/examples.py](scripts/examples.py) 与 [references/api_reference.md](references/api_reference.md)。

---

## 八、高级用法（开发者）

### 命令行直接传参（跳过向导，适合脚本）

```bash
mua run --product-id PID --pod-id POD --prompt "打开企业微信，回复最新客户消息" --gps --no-interactive
```

### GPS 定位注入（可选）

云手机无 GPS 硬件，可通过 `GpsInfo` 注入虚拟定位。仅当任务涉及位置（附近/地图/导航/外卖/打车等词）时自动询问，无关任务不打扰；`--gps` 可显式允许。

定位获取为**多来源统一接口 + 自动降级链**：文本坐标解析 → 图片 EXIF → macOS CoreLocation（米级，需权限）→ IP 定位（城市级）→ 地名地理编码 → 手动输入兜底。拒绝自动获取时仍可用提示词中的坐标/地名或手动输入。坐标系统一 WGS-84。详见 [references/gps.md](references/gps.md)。

### 目录结构

```
mobile-use-agent/
├── SKILL.md               # Skill 入口: 触发场景 + 安全边界 + 工作流
├── bin/mua                # 全局命令入口
├── install.sh             # 一键安装: 独立 Python 环境 + 精简装依赖 (约 1 分钟) + mua 命令
├── scripts/               # 可执行代码 + 可 import 的工具库
│   ├── cli.py             # 交互式 CLI + 命令行模式 (主入口)
│   ├── mobile_use_agent.py  # 核心客户端, 封装 10 个 OpenAPI
│   ├── error_codes.py     # 错误码定义与解析
│   ├── credential_store.py  # 凭证 + 默认手机持久化
│   ├── geo.py             # 定位获取 (6 来源统一抽象 + 自动降级链)
│   ├── make_slim_sdk.py   # 构建精简 SDK wheel (安装提速用, 见 install.sh)
│   └── templates.py       # 示例任务模板
├── references/            # 按需加载的参考文档
│   ├── commands.md        # 命令参考
│   ├── error_codes.md     # 错误码参考
│   ├── gps.md             # GPS 注入参考
│   └── api_reference.md   # OpenAPI 参考
└── requirements.txt       # Python 依赖
```

---

## 许可证

MIT
