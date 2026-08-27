# 错误码参考

数据来源: [火山引擎错误码文档](https://docs.volcengine.com/docs/6394/1956026)

所有 API 错误统一转换为 `MobileUseError` 异常（`scripts/error_codes.py`），携带:
- `code_n` / `code`: 数值 / 字符串错误码
- `desc`: 中文描述
- `advice`: 操作建议
- `category`: 分类 (auth / param / resource / task / hitl / model / tool / security / platform / system / unknown)
- `retryable`: 是否可重试

## 错误码表（摘要）

| 分类 | 典型错误码 | 含义 | CLI 引导 |
|---|---|---|---|
| 认证/授权 | `401 InvalidAccessKey` | AK/SK 无效 | 提示运行 `setup` 重配凭证 |
| 认证/授权 | `401100 ErrAssumeRoleFailed` | 跨服务未授权 | 提示去控制台授权 `ServiceName=ipaas` |
| 资源 | `400205 ErrCloudPhoneProductUnavailable` | ProductId 不存在/无权限 | 提示检查 ProductId |
| 资源 | `400206 ErrCloudPhonePodUnavailable` | PodId 不存在/不可用 | 提示检查 ProductId/PodId/实例状态 |
| 参数 | `400207 ErrCloudPhoneGPSInjectFailed` | GPS 注入失败 | 提示检查 GPS 参数 |
| 任务状态 | `400201 ErrTaskStillExecuting` | 任务仍在执行 | 轮询时自动继续等待 |
| 任务状态 | `4000001 AGENT_MAX_STEP_REACHED` | 步数超限 | 建议拆分任务 |
| 任务状态 | `4000003 AGENT_TIMEOUT` | 执行超时 | 建议检查卡顿 |
| 任务状态 | `4000004 AGENT_STUCK_LOOP` | 陷入死循环 | 建议终止任务调整提示词 |
| 人工介入 HITL | `5000001/5000002/5000003` | 需补充信息/审批/协助 | 提示人工介入流程 |
| 模型 | `6000001 MODEL_CALL_FAILED` | 模型调用失败 | 自动重试, 多次失败查额度 |
| 工具/环境 | `3000001 ENV_APP_NOT_INSTALLED` | App 未安装 | 提示安装 App 或改镜像 |
| 安全 | `9000001 SECURITY_BLOCKED` | 高风险操作被拦截 | 提示调整任务目标 |

完整表见 `scripts/error_codes.py`（公共 12 + 业务 32 + 平台认证 5）。

## 双通道错误捕获（关键陷阱）

SDK 只在 HTTP 非 2xx 时抛 `ApiException`；**HTTP 200 的业务错误**（如 Pod 不存在）会静默藏在响应体 `ResponseMetadata.Error` 里返回。客户端两层都做了适配，调用方只需捕获 `MobileUseError`：

```python
try:
    resp = client.run_agent_task_one_step(...)
except MobileUseError as e:
    print(e.desc)       # 中文描述
    print(e.advice)     # 操作建议
    print(e.category)   # 分类: auth/resource/task/hitl/...
```

## 任务失败自动归因

`run_and_wait` 轮询到 `GetAgentResult.IsSuccess=0` 时，自动扫描响应中的业务错误码并打印：

```
  [任务结束] 状态: 失败/未成功 (IsSuccess=0)
  [失败原因] 任务规划陷入死循环
  [操作建议] 终止任务并分析可观测链路, 调整提示词或任务目标
  [错误码]   4000004 AGENT_STUCK_LOOP
```

## 常见问题引导

- **凭证失效** (`InvalidAccessKey` / `SignatureDoesNotMatch` / `RequestExpired`): 运行 `python3 scripts/cli.py setup` 重新配置
- **跨服务未授权** (`ErrAssumeRoleFailed`): 访问 https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas 授权
- **可重试错误** (`ErrTaskStillExecuting` 等): `run_and_wait` 轮询会自动继续等待，无需干预
