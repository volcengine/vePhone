import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { ApiError, api } from "../api/client";
import type { TaskReport } from "../api/types";
import { StatusBadge } from "../components/status-badge";
import { failureTypeLabel } from "../utils/task-status";

function emptyFriendlyError(error: unknown) {
  if (!error) return null;
  if (error instanceof ApiError && error.message.includes("not configured")) return null;
  return error instanceof Error ? error.message : "报告加载失败";
}

function VerdictIcon({ verdict }: { verdict: string | null }) {
  if (verdict === "pass") {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--state-success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  }
  if (verdict === "fail") {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--state-error)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" /><path d="m15 9-6 6M9 9l6 6" />
      </svg>
    );
  }
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--state-warning)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><line x1="12" x2="12" y1="8" y2="12" /><line x1="12" x2="12.01" y1="16" y2="16" />
    </svg>
  );
}

export function TaskReportPage() {
  const { taskId } = useParams();
  const report = useQuery({
    enabled: Boolean(taskId),
    queryKey: ["task-report", taskId],
    queryFn: () => api.get<TaskReport>(`/tasks/${taskId}/report`),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      return false;
    },
    retry: (count, error) => {
      if (error instanceof ApiError && (error.status === 409 || error.code === "report_not_ready")) {
        return count < 30;
      }
      return false;
    },
  });

  if (report.isPending) return <div className="table-card"><p className="muted">正在生成报告...</p></div>;
  const friendlyError = emptyFriendlyError(report.error);
  if (friendlyError) return <div className="table-card"><p className="form-error">{friendlyError}</p></div>;
  if (!report.data) return <div className="table-card"><p className="muted">任务尚未完成，暂无报告。</p></div>;

  const data = report.data;

  return (
    <div className="report-page">
      <section className="table-card">
        <div className="section-heading">
          <h2>测试报告：{data.title}</h2>
          <StatusBadge verdict={data.verdict} />
        </div>

        <div className="report-verdict-hero">
          <div className="verdict-icon-wrap">
            <VerdictIcon verdict={data.verdict} />
          </div>
          <div className="verdict-body">
            <div className="verdict-title">
              {data.verdict === "pass" ? "执行成功" : "执行失败"}
            </div>
            {data.summary ? (
              <p className="verdict-summary">{data.summary}</p>
            ) : (
              <p className="muted">Agent 未返回摘要信息。</p>
            )}
            {data.failure_type && (
              <p className="form-error" style={{ marginTop: 8 }}>
                失败类型：{failureTypeLabel(data.failure_type)}
              </p>
            )}
          </div>
        </div>
      </section>

      {data.evidence && data.evidence.length > 0 && (
        <section className="table-card" style={{ marginTop: "1rem" }}>
          <div className="section-heading" style={{ marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1rem" }}>执行证据</h2>
            <span className="muted small">共 {data.evidence.length} 条</span>
          </div>
          <ul className="evidence-list">
            {data.evidence.map((item, idx) => (
              <li key={idx} className="evidence-item">
                <span className="evidence-index">{idx + 1}</span>
                <span className="evidence-text">{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
