import type {
  CronPreviewResponse,
  PlanExecutionResponse,
  ScheduleEventListResponse,
  TestPlanSchedule,
  TestPlanScheduleCreate,
  TestPlanScheduleUpdate,
} from "./types";

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
    details?: Record<string, unknown>;
  };
};

const unauthorizedListeners = new Set<() => void>();
let businessIdResolver: (() => string | null | undefined) | null = null;

export function subscribeUnauthorized(listener: () => void) {
  unauthorizedListeners.add(listener);
  return () => {
    unauthorizedListeners.delete(listener);
  };
}

export function setBusinessIdResolver(
  resolver: (() => string | null | undefined) | null,
) {
  businessIdResolver = resolver;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId: string,
    public details: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | undefined {
  const entry = document.cookie
    .split("; ")
    .find((candidate) => candidate.startsWith(`${name}=`));
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : undefined;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await rawRequest(path, init);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

async function rawRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const csrf = readCookie("csrf");
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (csrf && !headers.has("X-CSRF-Token")) {
    headers.set("X-CSRF-Token", csrf);
  }
  const businessId = businessIdResolver?.();
  if (businessId && !headers.has("X-Business-Id")) {
    headers.set("X-Business-Id", businessId);
  }

  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "same-origin",
    headers,
  });

  if (!response.ok) {
    let body: ErrorEnvelope = {};
    try {
      body = (await response.json()) as ErrorEnvelope;
    } catch {
      // Authentication probes can intentionally return an empty 401 response.
    }
    if (response.status === 401) {
      unauthorizedListeners.forEach((listener) => listener());
    }
    throw new ApiError(
      response.status,
      body.error?.code ?? "request_failed",
      body.error?.message ?? `请求失败 (${response.status})`,
      body.error?.request_id ?? "",
      body.error?.details ?? {},
    );
  }

  return response;
}

export const api = {
  get<T>(path: string) {
    return request<T>(path);
  },
  post<T>(path: string, body?: unknown, headers?: HeadersInit) {
    return request<T>(path, {
      method: "POST",
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  },
  postRaw<T>(path: string, body: BodyInit, headers?: HeadersInit) {
    return request<T>(path, {
      method: "POST",
      headers,
      body,
    });
  },
  put<T>(path: string, body: unknown, headers?: HeadersInit) {
    return request<T>(path, {
      method: "PUT",
      headers,
      body: JSON.stringify(body),
    });
  },
  patch<T>(path: string, body: unknown) {
    return request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  delete<T>(path: string) {
    return request<T>(path, { method: "DELETE" });
  },
  download(path: string) {
    return rawRequest(path);
  },
};

export const scheduleApi = {
  get(planId: string) {
    return api.get<TestPlanSchedule>(`/test-plans/${planId}/schedule`);
  },
  create(planId: string, body: TestPlanScheduleCreate) {
    return api.post<TestPlanSchedule>(
      `/test-plans/${planId}/schedule`,
      body,
    );
  },
  update(planId: string, body: TestPlanScheduleUpdate) {
    return api.put<TestPlanSchedule>(
      `/test-plans/${planId}/schedule`,
      body,
    );
  },
  delete(planId: string) {
    return api.delete<void>(`/test-plans/${planId}/schedule`);
  },
  enable(planId: string) {
    return api.post<TestPlanSchedule>(
      `/test-plans/${planId}/schedule/enable`,
    );
  },
  disable(planId: string) {
    return api.post<TestPlanSchedule>(
      `/test-plans/${planId}/schedule/disable`,
    );
  },
  run(planId: string) {
    return api.post<PlanExecutionResponse>(
      `/test-plans/${planId}/schedule/run`,
    );
  },
  events(planId: string, page = 1, pageSize = 20) {
    return api.get<ScheduleEventListResponse>(
      `/test-plans/${planId}/schedule/events?page=${page}&page_size=${pageSize}`,
    );
  },
  preview(cron: string, timezone: string, count = 5) {
    return api.get<CronPreviewResponse>(
      `/test-plans/schedule/preview?cron=${encodeURIComponent(cron)}&timezone=${encodeURIComponent(timezone)}&count=${count}`,
    );
  },
};
