const CHINA_DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

function normalizeTimestamp(value: string): string {
  const trimmed = value.trim();
  // Backend stores UTC but SQLite returns naive datetimes serialized without a
  // timezone designator. Treat such ISO strings as UTC so China time is correct.
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(trimmed)) {
    return `${trimmed.replace(" ", "T")}Z`;
  }
  return trimmed;
}

export function parseTimestampMs(value: string | null | undefined): number {
  if (!value) return Number.NaN;
  return Date.parse(normalizeTimestamp(value));
}

function parts(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(normalizeTimestamp(value));
  if (Number.isNaN(date.getTime())) return null;
  return Object.fromEntries(
    CHINA_DATE_TIME_FORMATTER
      .formatToParts(date)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  ) as Record<string, string>;
}

export function formatChinaDateTime(value: string | null | undefined): string {
  const p = parts(value);
  if (!p) return "-";
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`;
}

export function formatChinaDate(value: string | null | undefined): string {
  const p = parts(value);
  if (!p) return "-";
  return `${p.year}-${p.month}-${p.day}`;
}

export function formatElapsedTime(
  start: string | null | undefined,
  end: string | null | undefined,
  nowMs = Date.now(),
): string {
  if (!start) return "-";
  const startMs = parseTimestampMs(start);
  if (Number.isNaN(startMs)) return "-";
  const endMs = end ? parseTimestampMs(end) : nowMs;
  if (Number.isNaN(endMs)) return "-";
  const totalSeconds = Math.max(0, Math.floor((endMs - startMs) / 1000));
  return formatCompactDuration(totalSeconds);
}

export function formatTaskElapsedTime(
  executionStatus: string | null | undefined,
  start: string | null | undefined,
  end: string | null | undefined,
  nowMs = Date.now(),
): string {
  if (executionStatus === "queued") return "0 秒";
  return formatElapsedTime(start, end, nowMs);
}

export function formatDurationSeconds(
  value: number | null | undefined,
): string {
  if (value == null || !Number.isFinite(value) || value < 0) return "-";
  return formatCompactDuration(Math.floor(value));
}

function formatCompactDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours} 小时 ${String(minutes).padStart(2, "0")} 分 ${
      String(seconds).padStart(2, "0")
    } 秒`;
  }
  if (minutes > 0) return `${minutes} 分 ${seconds} 秒`;
  return `${seconds} 秒`;
}

export function recentWindowStartIso(days: number, nowMs = Date.now()): string {
  return new Date(nowMs - days * 24 * 60 * 60 * 1000).toISOString();
}
