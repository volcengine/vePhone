import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { transferableAbortController } from "node:util";
import { createElement, StrictMode } from "react";
import {
  createBrowserRouter,
  createMemoryRouter,
  RouterProvider,
} from "react-router";
import { afterAll, afterEach, beforeAll, beforeEach, expect } from "vitest";

import { App } from "../../web/app";

const NativeAbortController = transferableAbortController()
  .constructor as typeof AbortController;
globalThis.AbortController = NativeAbortController;
window.AbortController = NativeAbortController;

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(values.keys())[index] ?? null;
    },
    removeItem(key: string) {
      values.delete(key);
    },
    setItem(key: string, value: string) {
      values.set(key, String(value));
    },
  };
}

const localStorageMock = createMemoryStorage();
const sessionStorageMock = createMemoryStorage();

Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: localStorageMock,
});
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: localStorageMock,
});
Object.defineProperty(globalThis, "sessionStorage", {
  configurable: true,
  value: sessionStorageMock,
});
Object.defineProperty(window, "sessionStorage", {
  configurable: true,
  value: sessionStorageMock,
});

const activeRouters = new Set<ReturnType<typeof createMemoryRouter>>();

export const server = setupServer(
  http.get("/api/v1/setup/status", () => HttpResponse.json({ initialized: true })),
  http.get("/api/v1/auth/me", () =>
    HttpResponse.json({
      id: 1,
      username: "admin",
      display_name: null,
      email: null,
      role: "admin",
      status: "active",
      created_at: "2026-07-24T00:00:00Z",
      updated_at: "2026-07-24T00:00:00Z",
      last_login_at: null,
    }),
  ),
  http.get("/api/v1/business-spaces", () =>
    HttpResponse.json({
      items: [
        {
          id: "biz_default",
          name: "默认业务",
          description: null,
          is_default: true,
          task_concurrency_limit: 4,
          archived_at: null,
          created_by: "system",
        },
      ],
    }),
  ),
  http.get("/api/v1/tasks", () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 })),
  http.get("/api/v1/tasks/stats", () =>
    HttpResponse.json({ total: 0, running: 0, queued: 0, pass_rate: 0 }),
  ),
  http.get("/api/v1/tags", () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
  ),
  http.get("/api/v1/test-plans/tags", () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
  ),
  http.get("/api/v1/test-plans/creators", () => HttpResponse.json({ items: [] })),
  http.get("/api/v1/cases/stats", () =>
    HttpResponse.json({
      total: 0,
      auto_count: 0,
      today_executions: 0,
      total_executions: 0,
      pass_rate: 0,
    }),
  ),
  http.get("/api/v1/cases/creators", () => HttpResponse.json({ items: [] })),
  http.get("/api/v1/tasks/operators", () => HttpResponse.json({ items: [] })),
  http.get("/api/v1/tasks/:taskId/events", () => HttpResponse.json({ items: [] })),
  http.get("/api/v1/task-reports/:executionId", () =>
    HttpResponse.json(
      {
        error: {
          code: "task_report_not_found",
          message: "Task report not found",
        },
      },
      { status: 404 },
    )),
  http.get("/api/v1/test-plans/:planId/cases", () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
  ),
  http.get("/api/v1/cases/:caseId/test-plans", () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 5 }),
  ),
  http.get("/api/v1/agent-run-scripts", () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 }),
  ),
  http.get("/api/v1/agent-run-chains", () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 }),
  ),
  http.get("/api/v1/tasks/:taskId/runtime", ({ params }) => {
    const taskId = String(params.taskId);
    const task = {
      id: taskId,
      case_id: "case_1",
      script_version_id: null,
      prompt_snapshot: null,
      result_summary: null,
      result_evidence: [],
      remote_thread_id: null,
      remote_status_code: null,
      remote_step_id: null,
      recording_url: null,
      result_assets: {},
      runner_type: "mock",
      scenario: taskId,
      execution_status: "queued",
      verdict: null,
      failure_type: null,
      version: 1,
      created_at: "2026-07-24T00:00:00Z",
      started_at: null,
      finished_at: null,
    };
    return HttpResponse.json({
      task,
      current_step: null,
      thread_groups: [],
      thread_steps: [],
      trace: {
        task_id: taskId,
        source: "events",
        view: "tree",
        execution_status: "queued",
        verdict: null,
        failure_type: null,
        spans: [],
      },
      result: {
        summary: null,
        evidence: [],
        recording_url: null,
        assets: {},
      },
      errors: {},
    });
  }),
  http.get("/api/v1/settings", () =>
    HttpResponse.json({
      mode: "mock",
      mobile_use: {
        access_key_id: { configured: false },
        secret_access_key: { configured: false },
        product_id: null,
        account_id: null,
        sts_role_trn: null,
        stream_token_ttl_seconds: 600,
        pod_id: null,
        ark_api_key: { configured: false },
        tos_bucket: null,
        tos_endpoint: null,
        tos_region: null,
        use_base64_screenshot: false,
        max_step: 100,
        timeout_seconds: 120,
        callback_info: null,
        output_schema: null,
        retry_limit: 3,
        system_prompt: null,
        screen_record: false,
        mcp_json: null,
        max_output_tokens: null,
        gps_info: null,
        request_headers: { configured: false, names: [] },
      },
    }),
  ),
);

export const user = userEvent.setup();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  document.cookie = "csrf=test-csrf-token; path=/";
});
afterEach(() => {
  cleanup();
  activeRouters.forEach((router) => router.dispose());
  activeRouters.clear();
  server.resetHandlers();
});
afterAll(() => server.close());

export function expectCsrf(request: Request) {
  expect(request.headers.get("X-CSRF-Token")).toBe("test-csrf-token");
}

export function renderApp(
  path = "/",
  options: { browser?: boolean; strict?: boolean } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const app = createElement(App);
  if (options.browser) {
    const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (currentPath !== path) {
      window.history.replaceState(window.history.state, "", path);
    }
  }
  const router = options.browser
    ? createBrowserRouter([{ path: "*", element: app }])
    : createMemoryRouter(
        [{ path: "*", element: app }],
        { initialEntries: [path] },
      );
  activeRouters.add(router);
  const routedApp = createElement(RouterProvider, { router });
  const providedApp = createElement(
    QueryClientProvider,
    { client: queryClient },
    routedApp,
  );

  return render(
    options.strict
      ? createElement(StrictMode, null, providedApp)
      : providedApp,
  );
}
