import type { Task } from "../api/types";

export function taskStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    result_ready: "已完成",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
}

export function taskStatusTone(status: string): "success" | "running" | "neutral" {
  if (status === "result_ready") return "success";
  if (status === "running" || status === "queued") return "running";
  return "neutral";
}

export function taskResultLabel(task: Task): string {
  if (task.execution_status === "cancelled") return "取消";
  if (task.verdict === "pass") return "成功";
  if (task.verdict === "fail") return "失败";
  return "-";
}

export function taskResultTone(task: Task): "success" | "danger" | "neutral" {
  if (task.execution_status === "cancelled") return "neutral";
  if (task.verdict === "pass") return "success";
  if (task.verdict === "fail") return "danger";
  return "neutral";
}

export function failureTypeLabel(failureType: string | null | undefined): string {
  if (!failureType) return "-";
  const labels: Record<string, string> = {
    assertion_failed: "断言失败",
    device_prepare_failed: "设备启动前处理失败",
    device_unavailable: "设备不可用",
    evidence_missing: "证据缺失",
    pod_pool_discovery_failed: "设备池刷新失败",
    runner_interrupted: "执行中断",
  };
  return labels[failureType] ?? failureType;
}
