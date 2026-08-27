# 命令参考 (CLI)

所有命令通过全局命令 `mua` 执行（等价形式 `python3 scripts/cli.py ...`），自动加载本地凭证（`~/.mobile_use_agent/credentials.json`）。

> 还没有 `mua`？在 skill 根目录运行 `./install.sh`——它会创建独立 Python 环境并装好依赖，无需手动安装任何包。

## 凭证与默认手机管理

```sh
mua setup                # 配置/重新配置 AK/SK (SK 输入不回显; 可配置默认手机)
mua whoami               # 查看凭证状态 + 默认手机 (脱敏展示, 只读)
mua device               # 查看默认云手机 (ProductId/PodId)
mua device --clear       # 清除默认手机 (AK/SK 保留)
mua logout               # 删除本地保存的全部凭证
```

首次运行任意命令时会自动引导配置 AK/SK。

**默认手机机制**：`setup` 时可保存 ProductId/PodId 为默认手机；之后 `run` 直接回车沿用，无需每次查找。命令行 `--product-id/--pod-id` 始终优先于默认值。

**新手友好**：`run` 的任务描述处输入序号（如 `1`）可直接使用内置示例模板——企业应用场景（企业微信回客户消息/CRM 录入客户/钉钉考勤打卡/开票统计/进销存查库存/电商后台发货/OA 审批）覆盖不同业务职能线，演示"AI 替你干活"，生活场景（看桌面/发微信/刷抖音/找餐厅/查天气）快速上手，带 `*` 的示例需云手机预装对应 App；首次运行显示欢迎页；报错输出大白话"发生了什么/你该怎么办"；任务结束明确提示完成状态与用时。

## 任务操作

```sh
# 运行任务 (问答式向导: 先描述任务, 手机默认值回车沿用)
mua run

# 直接传参 (跳过向导)
mua run --product-id PID --pod-id POD --prompt "打开企业微信，回复最新客户消息"

# 完整参数
mua run --product-id PID --pod-id POD --prompt "..." \
    --run-name my-task --max-step 100 --timeout 300 --system-prompt "..." \
    --gps --no-interactive

# 查询 / 结果 / 取消 / 列表
mua status --run-id RUN_XXX
mua result --run-id RUN_XXX
mua cancel --run-id RUN_XXX
mua list [--run-id RUN_XXX] [--run-name NAME] [--page-size N] [--page-number N]
```

## 代理运行配置管理

```sh
mua config-create       # 创建代理运行配置
mua config-list         # 查询配置列表
mua config-delete       # 删除配置
```

## 快速脚本与示例

```sh
python3 scripts/run.py                     # 最简快速运行 (仅交互输入必要参数)
python3 scripts/examples.py                # 5 个编程式调用场景示例
python3 scripts/geo.py                     # 单独测试定位 (输出来源/坐标/GpsInfo)
```

## 凭证与默认手机优先级

命令行 `--ak/--sk` > 环境变量 `VOLC_ACCESSKEY`/`VOLC_SECRETKEY` > 本地凭证文件。
默认手机: 命令行 `--product-id/--pod-id` > 本地保存的默认值 > 交互输入。

## 任务过程实时打印

运行任务时步骤**实时增量打印**（每步只出现一次）：

```
  -- Step 1 [OK] 13:17:12 --
     [action] finished
     [content] 已打开企业微信, 并回复了最新一条客户消息, 任务完成。
     [result] 上一轮任务已经完成,结果是:已打开企业微信并回复客户消息。
  -- Step 2 [OK] 13:17:20 --
     [action] click
     [content] 点击'发送'按钮
     [result] 点击成功

  [任务结束] 状态: 成功
```

- `[OK]` = 步骤成功（StepResult.IsSuccess=true），`[FAIL]` = 失败
- 任务结束后自动拉取最终结果（状态/内容/截屏 TOS URL/用量）
- 任务失败自动归因：打印失败原因、操作建议、错误码

## 交互式菜单

```sh
mua     # 无参数进入菜单: 运行/状态/结果/取消/列表/配置管理
```

## GPS 定位注入

- **智能询问**：仅当提示词涉及位置（附近/地图/导航/外卖/打车/餐厅/路线 等触发词）时询问授权；无关任务自动跳过。
- `--gps`：显式授权注入（非交互模式唯一注入途径）。
- `--no-interactive`：跳过交互式参数确认（此时不注入 GPS，除非带 `--gps`）。

## 非交互模式

`--no-interactive` 跳过交互式参数确认；`--gps` 显式授权定位注入。
