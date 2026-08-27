import { useEffect, useState } from "react";
import { scheduleApi } from "../api/client";
import type { CronPreviewResponse } from "../api/types";

type CronInputProps = {
  value: string;
  timezone: string;
  onChange: (value: string) => void;
  error?: string | null;
};

const PRESET_OPTIONS = [
  { label: "每小时", cron: "0 * * * *" },
  { label: "每天 09:00", cron: "0 9 * * *" },
  { label: "工作日 09:00", cron: "0 9 * * 1-5" },
  { label: "每周日 02:00", cron: "0 2 * * 0" },
  { label: "每月 1 号 00:00", cron: "0 0 1 * *" },
];

export function CronInput({
  value,
  timezone,
  onChange,
  error,
}: CronInputProps) {
  const [preview, setPreview] = useState<CronPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (!value.trim()) {
      setPreview(null);
      setPreviewError(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await scheduleApi.preview(value.trim(), timezone);
        if (!cancelled) {
          setPreview(result);
          setPreviewError(null);
        }
      } catch {
        if (!cancelled) {
          setPreview(null);
          setPreviewError("无效的 cron 表达式");
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [value, timezone]);

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="text"
          className="form-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="分 时 日 月 周，如 0 9 * * 1-5"
          style={{ fontFamily: "monospace" }}
        />
      </div>
      <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
        {PRESET_OPTIONS.map((opt) => (
          <button
            key={opt.cron}
            type="button"
            className="ghost-button"
            style={{ fontSize: 11 }}
            onClick={() => onChange(opt.cron)}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {(error || previewError) && (
        <div style={{ color: "#dc2626", fontSize: 12, marginTop: 4 }}>
          {error || previewError}
        </div>
      )}
      {preview && !error && !previewError && (
        <div
          style={{
            marginTop: 6,
            padding: "6px 10px",
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: 4,
            fontSize: 12,
          }}
        >
          <div style={{ fontWeight: 500, color: "#166534" }}>
            {preview.human_description}
          </div>
          <div
            style={{
              color: "#6b7280",
              marginTop: 2,
              fontFamily: "monospace",
              fontSize: 11,
            }}
          >
            {preview.next_runs
              .slice(0, 3)
              .map((d) => new Date(d).toLocaleString("zh-CN"))
              .join("  →  ")}
          </div>
        </div>
      )}
    </div>
  );
}
