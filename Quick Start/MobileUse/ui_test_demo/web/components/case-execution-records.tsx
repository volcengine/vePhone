import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { TaskListPage } from "../api/types";
import { BusinessLink as Link } from "./business-link";
import { CopyButton } from "./copy-button";
import { formatChinaDateTime, formatTaskElapsedTime } from "../utils/time";
import { taskResultLabel, taskResultTone, taskStatusLabel, taskStatusTone } from "../utils/task-status";

const PAGE_SIZE = 5;

function isActiveStatus(status: string): boolean {
  return status === "queued" || status === "running";
}

function ChevronLeftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export function CaseExecutionRecords({ caseId }: { caseId: string }) {
  const [page, setPage] = useState(1);

  const tasksQuery = useQuery({
    queryKey: ["case-tasks", caseId, page],
    queryFn: () =>
      api.get<TaskListPage>(`/cases/${caseId}/tasks?page=${page}&page_size=${PAGE_SIZE}`),
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (!items) return false;
      return items.some((task) => isActiveStatus(task.execution_status)) ? 4000 : false;
    },
  });

  const items = tasksQuery.data?.items ?? [];
  const total = tasksQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="form-card exec-records-card">
      <div className="exec-records-head">
        <div className="sidebar-section-title" style={{ marginBottom: 0 }}>执行记录</div>
        {total > 0 && <span className="exec-records-count">{total} 条</span>}
      </div>

      {tasksQuery.isLoading ? (
        <div className="exec-records-empty">加载中...</div>
      ) : tasksQuery.isError ? (
        <div className="exec-records-empty error">
          加载失败：{tasksQuery.error instanceof ApiError ? tasksQuery.error.message : "未知错误"}
        </div>
      ) : total === 0 ? (
        <div className="exec-records-empty">该用例暂无执行记录</div>
      ) : (
        <>
          <div className="table-scroll">
            <table className="data-table exec-records-table">
              <thead>
                <tr>
                  <th style={{ width: 220 }}>任务ID</th>
                  <th style={{ width: 96 }}>状态</th>
                  <th style={{ width: 88 }}>执行结果</th>
                  <th style={{ width: 170 }}>创建时间</th>
                  <th style={{ width: 96 }}>执行时长</th>
                  <th style={{ width: 72, textAlign: "right" }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <div className="cell-id-copy">
                        <code className="mono cell-id-text" title={task.id}>{task.id}</code>
                        <CopyButton value={task.id} label="任务ID" />
                      </div>
                    </td>
                    <td>
                      <span className={`badge-tag ${taskStatusTone(task.execution_status)}`}>
                        {taskStatusLabel(task.execution_status)}
                      </span>
                    </td>
                    <td>
                      <span className={`badge-tag ${taskResultTone(task)}`}>
                        {taskResultLabel(task)}
                      </span>
                    </td>
                    <td className="muted cell-nowrap">{formatChinaDateTime(task.created_at)}</td>
                    <td className="muted cell-nowrap">
                      {formatTaskElapsedTime(task.execution_status, task.started_at, task.finished_at)}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <Link className="text-button" to={`/tasks/${task.id}`}>查看</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="pagination">
              <button
                type="button"
                className="page-button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeftIcon />
              </button>
              <span className="page-info">第 {page} / {totalPages} 页</span>
              <button
                type="button"
                className="page-button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                <ChevronRightIcon />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
