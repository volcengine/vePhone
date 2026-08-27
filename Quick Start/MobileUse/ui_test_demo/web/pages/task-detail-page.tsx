import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useParams } from "react-router";

import { ApiError, api } from "../api/client";
import type { Task } from "../api/types";
import { useBusinessPath } from "../business-context";
import { PageHeader } from "../components/page-header";
import { StatusBadge } from "../components/status-badge";

function FileTextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function ActivityIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function emptyFriendlyError(error: unknown) {
  if (!error) return null;
  if (error instanceof ApiError && error.message.includes("not configured")) return null;
  return error instanceof Error ? error.message : "任务详情加载失败";
}

function mapStatus(status: string) {
  return status;
}

export function TaskDetailPage() {
  const { taskId } = useParams();
  const businessPath = useBusinessPath();
  const task = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task", taskId],
    queryFn: () => api.get<Task>(`/tasks/${taskId}`),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      return ["result_ready", "cancelled"].includes(data.execution_status)
        ? false
        : 3000;
    },
  });

  if (task.isPending) return <p className="panel">正在加载任务详情...</p>;
  const friendlyError = emptyFriendlyError(task.error);
  if (friendlyError) return <p className="panel form-error">{friendlyError}</p>;
  if (!task.data) return <p className="panel form-error">任务不存在</p>;

  const item = task.data;

  return (
    <div className="detail-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "执行记录", to: "/tasks" },
          { label: "任务详情" },
        ]}
        title={`${item.scenario} 测试`}
        description={(
          <>
            任务 ID <code className="mono">{item.id}</code> · 场景 {item.scenario}
          </>
        )}
        actions={
          <>
          <StatusBadge status={mapStatus(item.execution_status)} />
          {item.verdict && <StatusBadge verdict={item.verdict} />}
          </>
        }
      />

      <nav className="detail-tabs detail-tabs-full" aria-label="任务详情导航">
        <NavLink end to={businessPath(`/tasks/${item.id}`)}>
          <FileTextIcon />
          概览
        </NavLink>
        <NavLink to={businessPath(`/tasks/${item.id}/trace`)}>
          <ActivityIcon />
          执行轨迹
        </NavLink>
      </nav>
      <div className="tab-content tab-content-full">
        <Outlet />
      </div>
    </div>
  );
}
