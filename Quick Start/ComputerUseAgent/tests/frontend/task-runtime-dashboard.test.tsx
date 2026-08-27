import { readFileSync } from "node:fs";
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, delay, http } from "msw";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { renderApp, server, user } from "./setup";

const STYLES = readFileSync("web/styles.css", "utf8");

const task = {
  id: "task_runtime",
  case_id: "case_1",
  script_version_id: null,
  prompt_snapshot: "## 执行任务\n打开抖音APP查看3个视频",
  result_summary: "已打开抖音并完成浏览",
  result_evidence: ["首页出现视频流", "已滑动 3 个视频"],
  remote_run_id: "run-1",
  remote_thread_id: "thread-123",
  remote_status_code: 3,
  remote_step_id: "finished",
  recording_url: "https://example.invalid/replay.mp4",
  result_assets: {
    usage: { in_tokens: 100, out_tokens: 20 },
    screenshots: {
      "348347930101403648-0": { screenshot: "https://example.invalid/s0.png" },
      "348347930101403648-1": { screenshot: "https://example.invalid/s1.png" },
      "348347930101403648-10": { original_screenshot: "https://example.invalid/s10-original.png" },
      "348347930101403648-2": { screenshot: "https://example.invalid/s2.png" },
    },
    files: ["/sdk_files/run-1/log.txt", "/sdk_files/run-1/result.json"],
    duration_ms: 125000,
  },
  runner_type: "mobile_use",
  scenario: "打开抖音APP查看3个视频",
  execution_config: {
    source: "custom",
    account_id: "2107192146",
    product_id: null,
    pod_id: "i-yershysetc5i3z3ma1n6",
    tos_bucket: "custom-bucket",
    tos_endpoint: "tos-s3-cn-beijing.volces.com",
    tos_region: "cn-beijing",
    timeout_seconds: 456,
    use_base64_screenshot: null,
    max_step: 123,
    callback_info: { url: "https://callback.example.com" },
    output_schema: "{\"type\":\"object\"}",
    retry_limit: 7,
    system_prompt: "custom system prompt",
    screen_record: null,
    mcp_json: "{\"mcpServers\":{\"amap\":{\"url\":\"https://mcp.example.com\"}}}",
    max_output_tokens: 2048,
    gps_info: null,
    request_headers: {
      configured: true,
      names: ["X-Env", "X-Api-Key"],
      items: [
        { name: "X-Env", value: "staging" },
        { name: "X-Api-Key", value: "sk_l***cdef" },
      ],
    },
  },
  execution_status: "result_ready",
  verdict: "pass",
  failure_type: null,
  version: 4,
  created_at: "2026-07-28T03:35:31.564869Z",
  started_at: "2026-07-28T03:35:31.575333Z",
  finished_at: "2026-07-28T03:38:32.263965Z",
  created_by: "admin",
};

const caseResponse = {
  id: "case_1",
  title: "账号视频流回归",
  module: "账号",
  content_markdown:
    "## 执行任务\n1. 打开目标 App\n2. 进入首页视频流\n3. 连续浏览 3 个视频\n\n## 预期结果\n- 视频流可正常加载",
  tags: ["P0", "回归"],
  automation_level: "auto",
  default_agent_options: null,
  execution_count: 4,
  pass_count: 3,
  fail_count: 1,
  last_executed_at: "2026-07-29T12:03:00Z",
  created_by: "admin",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-29T12:03:00Z",
};

beforeEach(() => {
  vi.stubGlobal("Image", class {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;

    set src(_value: string) {
      queueMicrotask(() => this.onload?.());
    }
  });
  server.use(
    http.get("/api/v1/cases/case_1", () => HttpResponse.json(caseResponse)),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function runtimePayload() {
  return {
    task,
    execution_config: task.execution_config,
    current_step: {
      run_id: "run-1",
      thread_id: "thread-123",
      status: 3,
      step_id: "finished",
      results: [
        {
          Action: "finished",
          Param: { content: "任务已完成" },
          StepResult: { IsSuccess: true, Result: "任务已完成" },
          Timestamp: "2026-07-28T11:38:32+08:00",
        },
      ],
    },
    thread_groups: [
      {
        thread_id: "thread-123",
        task_next_token: null,
        tasks: [
          {
            run_id: "run-1",
            thread_id: "thread-123",
            run_name: "打开抖音",
            status: 3,
            pod_id: "pod-1",
            product_id: "prod-1",
            created_at: "2026-07-28 11:35:31 +0800 CST",
            started_at: "2026-07-28 11:35:32 +0800 CST",
            updated_at: "2026-07-28 11:38:32 +0800 CST",
            completed_at: "2026-07-28 11:38:32 +0800 CST",
            trace_id: "trace-1",
            artifact_count: { Screenshot: 3, Video: 1 },
          },
        ],
      },
    ],
    thread_steps: [
      {
        run_id: "run-1",
        thread_id: "thread-123",
        status: 3,
        step_id: "finished",
        results: [
          {
            Action: "tap",
            Param: { x: 100, y: 200 },
            StepResult: { IsSuccess: true, Result: "点击成功" },
            Timestamp: "2026-07-28T11:36:00+08:00",
          },
        ],
      },
    ],
    result: {
      summary: "已打开抖音并完成浏览",
      evidence: ["首页出现视频流", "已滑动 3 个视频"],
      recording_url: "https://example.invalid/replay.mp4",
      assets: task.result_assets,
    },
    errors: {},
  };
}

it("renders result-first overview with four KPIs, carousel screenshots and separated files", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
  let caseRequests = 0;
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(task)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json(runtimePayload()),
    ),
    http.get("/api/v1/cases/case_1", () => {
      caseRequests += 1;
      return HttpResponse.json(caseResponse);
    }),
  );

  renderApp("/tasks/task_runtime");

  expect(await screen.findByText("运行总览")).toBeVisible();
  const meta = screen.getByLabelText("运行元信息");
  expect(meta).toHaveClass("runtime-metric-strip");
  expect(meta).toHaveClass("runtime-metric-strip--bare");
  expect(meta).toHaveClass("runtime-metric-strip--full-labels");
  expect(meta.querySelectorAll(".runtime-metric-pill")).toHaveLength(5);
  expect(meta.querySelectorAll(".runtime-metric-glyph")).toHaveLength(5);
  expect(meta.querySelector(".runtime-metric-pill.status")).toBeInTheDocument();
  expect(meta.querySelector(".runtime-metric-pill.token-in")).toBeInTheDocument();
  expect(meta.querySelector(".runtime-metric-pill.token-out")).toBeInTheDocument();
  expect(meta.querySelector(".runtime-metric-pill.duration")).toBeInTheDocument();
  expect(meta.querySelector(".runtime-metric-pill.steps")).toBeInTheDocument();
  expect(meta.querySelector(".runtime-kpi-card")).not.toBeInTheDocument();
  expect(within(meta).getByText("远端状态")).toBeVisible();
  expect(within(meta).getByText("输入 Tokens")).toBeVisible();
  expect(within(meta).getByText("输出 Tokens")).toBeVisible();
  expect(within(meta).getByText("运行总时间")).toBeVisible();
  expect(within(meta).getByText("执行步数")).toBeVisible();
  expect(within(meta).getByText("成功")).toBeVisible();
  expect(within(meta).getByText("100")).toBeVisible();
  expect(within(meta).getByText("20")).toBeVisible();
  expect(within(meta).getByText("2 分 5 秒")).toBeVisible();
  await waitFor(() => expect(within(meta).getByText("1")).toBeVisible());
  expect(within(meta).queryByText("ThreadID")).not.toBeInTheDocument();
  expect(within(meta).queryByText("RunID")).not.toBeInTheDocument();

  const resultCard = screen.getByText("执行结果").closest("section");
  expect(resultCard).not.toBeNull();
  expect(within(resultCard!).getByText("成功")).toBeVisible();
  expect(screen.getByText("已打开抖音并完成浏览")).toBeVisible();
  expect(screen.queryByText("录制回放")).not.toBeInTheDocument();
  expect(screen.queryByText("查看录制回放")).not.toBeInTheDocument();
  expect(document.querySelector("video")).not.toBeInTheDocument();
  const detailNavigation = screen.getByRole("navigation", {
    name: "任务详情导航",
  });
  expect(within(detailNavigation).queryByRole("link", { name: /报告/ }))
    .not.toBeInTheDocument();
  expect(screen.queryByText("当前步骤")).not.toBeInTheDocument();
  expect(screen.getByText("执行截图")).toBeVisible();
  expect(screen.getByText("1 / 4")).toBeVisible();
  const image = screen.getByRole("img", { name: "截图 1" });
  expect(image).toHaveAttribute(
    "src",
    "https://example.invalid/s0.png",
  );
  await user.click(image);
  const previewDialog = screen.getByRole("dialog", { name: "截图 1 预览" });
  expect(within(previewDialog).getByRole("img", { name: "截图 1" }))
    .toHaveAttribute("src", "https://example.invalid/s0.png");
  await user.click(
    within(previewDialog).getByRole("button", { name: "关闭截图预览" }),
  );
  expect(screen.queryByRole("dialog", { name: "截图 1 预览" }))
    .not.toBeInTheDocument();
  // Expired screenshots are dropped from the viewer instead of showing a placeholder.
  fireEvent.error(image);
  expect(screen.getByText("1 / 3")).toBeVisible();
  expect(screen.queryByText("截图已过期或无法访问")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "下一张截图" }));
  expect(screen.getByText("2 / 3")).toBeVisible();
  expect(screen.getByRole("img", { name: "截图 2" })).toHaveAttribute(
    "src",
    "https://example.invalid/s2.png",
  );
  await user.click(screen.getByRole("button", { name: "上一张截图" }));
  expect(screen.getByText("1 / 3")).toBeVisible();

  expect(screen.getByText("结果文件")).toBeVisible();
  expect(screen.getByText("/sdk_files/run-1/log.txt")).toBeVisible();
  expect(screen.getByText("/sdk_files/run-1/result.json")).toBeVisible();
  const caseContentCard = await screen.findByRole("region", { name: "用例内容" });
  expect(caseRequests).toBe(1);
  expect(within(caseContentCard).getByText("账号视频流回归")).toBeVisible();
  expect(within(caseContentCard).getByText("账号")).toBeVisible();
  expect(within(caseContentCard).getByText(/进入首页视频流/)).toBeVisible();
  const expandCase = within(caseContentCard).getByRole("button", {
    name: "展开用例内容",
  });
  expect(expandCase).toHaveAttribute("aria-expanded", "false");
  await user.click(expandCase);
  expect(expandCase).toHaveAttribute("aria-expanded", "true");
  await user.click(within(caseContentCard).getByRole("button", {
    name: "复制用例内容",
  }));
  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("## 执行任务"))
  );
  const taskInfoCard = screen.getByText("任务信息").closest("section");
  expect(taskInfoCard).not.toBeNull();
  expect(within(taskInfoCard!).getAllByText("2026-07-28 11:35:31")).toHaveLength(2);
  expect(within(taskInfoCard!).getByText("2026-07-28 11:38:32")).toBeVisible();
  expect(within(taskInfoCard!).queryByText("版本")).not.toBeInTheDocument();

  const configCard = screen.getByText("运行配置快照").closest("section");
  expect(configCard).not.toBeNull();
  expect(within(configCard!).getByText("自定义配置")).toBeVisible();
  expect(within(configCard!).getByText("AccountID")).toBeVisible();
  expect(within(configCard!).getByText("2107192146")).toBeVisible();
  expect(within(configCard!).getByText("Ecsid")).toBeVisible();
  expect(within(configCard!).getByText("i-yershysetc5i3z3ma1n6")).toBeVisible();
  expect(within(configCard!).getByText("执行边界")).toBeVisible();
  expect(within(configCard!).getByText("存储与扩展")).toBeVisible();
  expect(within(configCard!).queryByText("采集能力")).not.toBeInTheDocument();
  expect(within(configCard!).queryByText("屏幕录制")).not.toBeInTheDocument();
  expect(within(configCard!).queryByText("Base64 截图")).not.toBeInTheDocument();
  expect(within(configCard!).queryByText("GPS")).not.toBeInTheDocument();
  expect(within(configCard!).queryByText("PodID")).not.toBeInTheDocument();
  expect(within(configCard!).getByText("456 s")).toBeVisible();
  const headerRow = within(configCard!).getByText("请求 Header")
    .closest(".runtime-config-row");
  expect(headerRow).not.toBeNull();
  const headerButton = within(headerRow as HTMLElement).getByRole("button", {
    name: "查看请求 Header",
  });
  expect(headerButton).toHaveTextContent("已设置");
  expect(within(configCard!).queryByText("输出结构")).not.toBeInTheDocument();
  expect(within(configCard!).queryByText("SystemPrompt", { selector: ".runtime-config-row span" }))
    .not.toBeInTheDocument();
  await user.click(headerButton);
  const headerDialog = await screen.findByRole("dialog", { name: "请求 Header" });
  expect(within(headerDialog).getByText("X-Env")).toBeVisible();
  expect(within(headerDialog).getByText("staging")).toBeVisible();
  expect(within(headerDialog).getByText("X-Api-Key")).toBeVisible();
  expect(within(headerDialog).getByText("sk_l***cdef")).toBeVisible();
  expect(within(headerDialog).getByText("Header 值已按敏感字段规则脱敏。"))
    .toBeVisible();
  await user.click(
    within(headerDialog).getByRole("button", { name: "关闭请求 Header 弹窗" }),
  );
  expect(screen.queryByRole("dialog", { name: "请求 Header" })).not.toBeInTheDocument();
  expect(within(configCard!).queryByText("custom system prompt")).not.toBeInTheDocument();

  const advancedButton = within(configCard!).getByRole("button", {
    name: "查看高级配置",
  });
  expect(advancedButton).toHaveAttribute("aria-expanded", "false");
  await user.click(advancedButton);
  expect(advancedButton).toHaveAttribute("aria-expanded", "true");
  expect(within(configCard!).getByRole("heading", { name: "SystemPrompt" })).toBeVisible();
  expect(within(configCard!).getByRole("heading", { name: "OutputSchema" })).toBeVisible();
  expect(within(configCard!).getByText("custom system prompt")).toBeVisible();
  expect(within(configCard!).getByText(/mcpServers/)).toBeVisible();
  expect(screen.queryByText("Thread 轨迹")).not.toBeInTheDocument();
  expect(screen.queryByText("tap")).not.toBeInTheDocument();
});

it("gives long execution results more desktop width while task info spans full width", () => {
  expect(STYLES).toMatch(
    /\.task-overview-layout\s*{[^}]*grid-template-columns:\s*minmax\(0, 1\.35fr\) minmax\(360px, 0\.65fr\);[^}]*}/,
  );
  expect(STYLES).toMatch(
    /\.task-overview-result\s*{\s*grid-column:\s*1;\s*grid-row:\s*1 \/ span 2;\s*}/,
  );
  expect(STYLES).toMatch(
    /\.task-overview-screenshots\s*{\s*grid-column:\s*2;\s*}/,
  );
  expect(STYLES).toMatch(
    /\.task-overview-files\s*{\s*grid-column:\s*2;\s*}/,
  );
  expect(STYLES).toMatch(
    /\.task-overview-meta\s*{\s*grid-column:\s*1 \/ -1;\s*}/,
  );
});

it("labels inherited snapshots as global configuration", async () => {
  const globalExecutionConfig = {
    ...task.execution_config,
    source: "global",
    pod_id: null,
    callback_info: null,
    output_schema: null,
    mcp_json: null,
    gps_info: null,
    request_headers: { configured: false, names: [] },
  };
  const globalTask = {
    ...task,
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(globalTask)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json({
        ...runtimePayload(),
        task: globalTask,
        execution_config: globalExecutionConfig,
      }),
    ),
  );

  renderApp("/tasks/task_runtime");

  const configCard = (await screen.findByText("运行配置快照")).closest("section");
  expect(configCard).not.toBeNull();
  expect(within(configCard!).getByText("全局配置")).toBeVisible();
  expect(within(configCard!).getByText(/任务创建时继承的全局配置快照/)).toBeVisible();
  expect(within(configCard!).getByText("自动分配")).toBeVisible();
});

it("shows specified Ecsids when a batch task has no allocated single Ecsid yet", async () => {
  const specifiedExecutionConfig = {
    ...task.execution_config,
    source: "global",
    pod_id: null,
    device_strategy: "specified",
    pod_ids: ["i-cua-a", "i-cua-b"],
  };
  const specifiedTask = {
    ...task,
    execution_config: specifiedExecutionConfig,
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(specifiedTask)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json({
        ...runtimePayload(),
        task: specifiedTask,
        execution_config: specifiedExecutionConfig,
      }),
    ),
  );

  renderApp("/tasks/task_runtime");

  const configCard = (await screen.findByText("运行配置快照")).closest("section");
  expect(configCard).not.toBeNull();
  const ecsidBlock = within(configCard!).getByText("Ecsid").closest("div");
  expect(ecsidBlock).not.toBeNull();
  expect(within(ecsidBlock as HTMLElement).getByText("i-cua-a, i-cua-b"))
    .toBeVisible();
  expect(within(ecsidBlock as HTMLElement).queryByText("自动分配"))
    .not.toBeInTheDocument();
});

it("uses GetAgentResult TotalSteps and explains screenshots without URLs", async () => {
  const completedTask = {
    ...task,
    result_assets: {
      usage: { in_tokens: 10, out_tokens: 2 },
    },
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(completedTask)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json({
        ...runtimePayload(),
        task: completedTask,
        thread_steps: [],
        result: {
          summary: "执行完成",
          evidence: [],
          recording_url: null,
          assets: {
            usage: { in_tokens: 10, out_tokens: 2 },
            total_steps: 4,
            screenshots: {
              "run-runtime-0": {
                id: "run-runtime-0",
                original_dimensions: [1440, 900],
                screenshot_dimensions: [1440, 900],
              },
              "run-runtime-1": {
                id: "run-runtime-1",
                original_dimensions: [1440, 900],
                screenshot_dimensions: [1440, 900],
              },
            },
          },
        },
      }),
    ),
  );

  renderApp("/tasks/task_runtime");

  const meta = await screen.findByLabelText("运行元信息");
  await waitFor(() =>
    expect(within(meta).getByText("执行步数").nextElementSibling).toHaveTextContent("4"),
  );
  expect(await screen.findByText("已返回 2 张截图，但没有可访问 URL。")).toBeVisible();
});

it("uses realtime screenshots instead of cached task assets", async () => {
  const cachedTask = {
    ...task,
    result_assets: {
      ...task.result_assets,
      screenshots: {
        "cached-0": { screenshot: "https://example.invalid/cached.png" },
      },
    },
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(cachedTask)),
    http.get("/api/v1/tasks/task_runtime/runtime", async () => {
      await delay(80);
      return HttpResponse.json({
        ...runtimePayload(),
        task: cachedTask,
        result: {
          ...runtimePayload().result,
          assets: {
            screenshots: {
              "remote-0": {
                id: "remote-0",
                original_dimensions: [1440, 900],
                screenshot_dimensions: [1440, 900],
              },
            },
          },
        },
      });
    }),
  );

  renderApp("/tasks/task_runtime");

  expect(await screen.findByText("运行总览")).toBeVisible();
  expect(screen.getByText("正在加载执行截图...")).toBeVisible();
  expect(screen.queryByRole("img", { name: "截图 1" })).not.toBeInTheDocument();

  expect(await screen.findByText("已返回 1 张截图，但没有可访问 URL。"))
    .toBeVisible();
  expect(screen.queryByRole("img", { name: "截图 1" })).not.toBeInTheDocument();
});

it("does not render the screenshot carousel before all expired URLs are checked", async () => {
  const pendingImages: Array<{
    onerror: (() => void) | null;
  }> = [];
  vi.stubGlobal("Image", class {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;

    set src(_value: string) {
      pendingImages.push(this);
    }
  });
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(task)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json(runtimePayload()),
    ),
  );

  renderApp("/tasks/task_runtime");

  expect(await screen.findByText("正在加载执行截图...")).toBeVisible();
  expect(screen.queryByRole("img", { name: "截图 1" })).not.toBeInTheDocument();
  await waitFor(() => expect(pendingImages).toHaveLength(4));

  await act(async () => {
    pendingImages.forEach((image) => image.onerror?.());
  });

  expect(await screen.findByText("已返回 4 张截图，但没有可访问 URL。"))
    .toBeVisible();
  expect(screen.queryByRole("img", { name: "截图 1" })).not.toBeInTheDocument();
});

it("shows persisted RunID when thread task detail is unavailable", async () => {
  const taskWithRun = {
    ...task,
    remote_run_id: "345569823413460992",
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(taskWithRun)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json({
        ...runtimePayload(),
        task: taskWithRun,
        thread_groups: [],
      }),
    ),
  );

  renderApp("/tasks/task_runtime");

  expect(await screen.findByText("RunID")).toBeVisible();
  expect(screen.getByText("345569823413460992")).toBeVisible();
});

it("updates running duration from local timestamps", async () => {
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
  try {
    vi.setSystemTime(new Date("2026-07-28T03:36:01.000Z"));
    const runningTask = {
      ...task,
      execution_status: "running",
      remote_status_code: 2,
      started_at: "2026-07-28T03:35:31.000Z",
      finished_at: null,
      verdict: null,
    };

    server.use(
      http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(runningTask)),
      http.get("/api/v1/tasks/task_runtime/runtime", () =>
        HttpResponse.json({
          ...runtimePayload(),
          task: runningTask,
          current_step: {
            ...runtimePayload().current_step,
            status: 2,
          },
        }),
      ),
    );

    const { container } = renderApp("/tasks/task_runtime");

    const meta = await screen.findByLabelText("运行元信息");
    expect(within(meta).getByText("30 秒")).toBeVisible();
    expect(container.querySelector(".runtime-metric-pill.steps strong")).toHaveTextContent("-");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(within(meta).getByText("35 秒")).toBeVisible();
  } finally {
    vi.useRealTimers();
  }
});

it("keeps queued task duration at zero instead of counting from creation", async () => {
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
  try {
    vi.setSystemTime(new Date("2026-07-28T04:36:01.000Z"));
    const queuedTask = {
      ...task,
      execution_status: "queued",
      remote_status_code: 1,
      created_at: "2026-07-28T03:35:31.000Z",
      started_at: null,
      finished_at: null,
      verdict: null,
    };

    server.use(
      http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(queuedTask)),
      http.get("/api/v1/tasks/task_runtime/runtime", () =>
        HttpResponse.json({
          ...runtimePayload(),
          task: queuedTask,
          current_step: null,
        }),
      ),
    );

    renderApp("/tasks/task_runtime");

    const meta = await screen.findByLabelText("运行元信息");
    expect(within(meta).getByText("0 秒")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(within(meta).getByText("0 秒")).toBeVisible();
    expect(within(meta).queryByText("01:00:35")).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

it("maps remote success result codes to success label", async () => {
  const completedNoMessage = {
    ...task,
    remote_status_code: 3,
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(completedNoMessage)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json({
        ...runtimePayload(),
        task: completedNoMessage,
        current_step: null,
      }),
    ),
  );

  renderApp("/tasks/task_runtime");

  let meta = await screen.findByLabelText("运行元信息");
  expect(within(meta).getByText("成功")).toBeVisible();
});

it("maps stopped remote result codes to stopped label", async () => {
  const stopped = {
    ...task,
    remote_status_code: 5,
    execution_status: "cancelled",
    verdict: null,
  };
  server.use(
    http.get("/api/v1/tasks/task_runtime", () => HttpResponse.json(stopped)),
    http.get("/api/v1/tasks/task_runtime/runtime", () =>
      HttpResponse.json({
        ...runtimePayload(),
        task: stopped,
        current_step: null,
      }),
    ),
  );

  renderApp("/tasks/task_runtime");

  const meta = await screen.findByLabelText("运行元信息");
  expect(within(meta).getByText("已停止")).toBeVisible();
});
