# OpenAPI 接口参考

服务: `ipaas` | 版本: `2023-08-01` | 端点: `open.volcengineapi.com` | 区域: `cn-north-1`

SDK: `volcengine-python-sdk`（模块 `volcenginesdkcore`），使用 `Configuration` + `UniversalApi` + `UniversalInfo` + `Flatten` 做通用调用。

## 接口列表

| 客户端方法 | Action | 方法 | 说明 |
|---|---|---|---|
| `create_agent_run_config` | CreateAgentRunConfig | POST | 创建代理运行配置 |
| `update_agent_run_config` | UpdateAgentRunConfig | POST | 更新代理运行配置 |
| `delete_agent_run_config` | DeleteAgentRunConfig | POST | 删除代理运行配置 |
| `list_agent_run_config` | ListAgentRunConfig | GET | 查询代理运行配置列表 |
| `run_agent_task` | RunAgentTask | POST | 运行代理任务 (需 ConfigId) |
| `run_agent_task_one_step` | RunAgentTaskOneStep | POST | 一键运行代理任务 (无需配置, 最便捷) |
| `cancel_task` | CancelTask | POST | 取消代理任务 |
| `list_agent_run_current_step` | ListAgentRunCurrentStep | GET | 查询任务当前步骤 |
| `list_agent_run_task` | ListAgentRunTask | GET | 查询代理任务列表 |
| `get_agent_result` | GetAgentResult | GET | 获取任务运行结果 |

## RunAgentTaskOneStep 核心参数

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|---|---|---|---|---|
| `RunName` | String | 是 | — | 运行名称 (1~127 字节) |
| `PodId` | String | 是 | — | 云手机实例 ID (每次传入) |
| `ProductId` | String | 是 | — | 云手机业务 ID (每次传入) |
| `UserPrompt` | String | 是 | — | 用户提示词 (每次传入, 最多 10000 字节) |
| `ThreadId` | String | 否 | 自动生成 | 线程 ID |
| `UseBase64Screenshot` | Boolean | 否 | false | Base64 编码传输截屏 |
| `MaxStep` | Integer | 否 | 100 | 最大步数 (1~500 或 -1) |
| `Timeout` | Integer | 否 | 120 | 超时秒数 (1~86400 或 -1) |
| `RetryLimit` | Integer | 否 | 3 | 失败重试次数 (0~10) |
| `SystemPrompt` | String | 否 | — | 系统提示词 (最多 20000 字符) |
| `TosBucket` | String | 否 | — | TOS 存储桶名称 |
| `TosEndpoint` | String | 否 | — | TOS 端点地址 |
| `TosRegion` | String | 否 | — | TOS 区域 |
| `IsScreenRecord` | Boolean | 否 | false | 是否开启录屏 |
| `McpJson` | String | 否 | — | 第三方 MCP 工具配置 (JSON) |
| `MaxOutputTokens` | Integer | 否 | 0 | 单次最大输出 Token 数 |
| `GpsInfo` | String | 否 | — | GPS 注入信息 (WGS-84, 英文逗号分隔 6 字段) |
| `OutputSchema` | String | 否 | — | 输出格式 (JSON 字符串) |
| `CallbackInfo` | dict | 否 | — | 回调配置 |

## ListAgentRunCurrentStep 响应结构（关键陷阱）

```
Result.Results[]          ← 步骤列表 (不是 Steps!)
  ├── Action              ← 如 "finished" / "click"
  ├── Param               ← {content: "操作描述"}
  ├── StepResult          ← {IsSuccess, Result}
  └── Timestamp           ← 步骤完成时间
```

客户端 `extract_results()` 已兼容嵌套/扁平两种形态；`format_step()` 增量打印去重。

## GetAgentResult 响应结构

```
IsSuccess    ← int, 1=成功结束 (终态判断用这个)
Content      ← 最终内容
StructOutput ← 结构化输出
ScreenShots  ← dict, IsDetail=true 时含截屏 TOS URL
Usage        ← 用量
```

## 前置条件

1. 火山引擎账号 — 完成注册和实名认证
2. 获取 AK/SK — 火山引擎控制台 → 右上角头像 → 访问密钥
3. 跨服务授权 — https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas
4. 云手机实例 — 云手机控制台创建业务 (ProductId) 和实例 (PodId)
5. (可选) 对象存储 TOS — 如需存储截图/录屏

## 注意事项

- **QPS 限制**: RunAgentTaskOneStep 整体 QPS 50 次/秒，单用户 10 次/秒
- **MaxStep=-1 + Timeout=-1**: 任务 7×24 持续运行，需手动 CancelTask 终止
- **录屏文件**: 有效期 24 小时，需配置 TOS 存储
- **默认 TOS**: 不传 TOS 参数时使用默认存储，任务完成后立即删除截图
