import { useCallback, useEffect, useRef, useState } from "react";

function CopyIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function copyWithExecCommand(value: string): void {
  if (typeof document.execCommand !== "function") {
    throw new Error("clipboard_unavailable");
  }
  const activeElement = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null;
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("aria-hidden", "true");
  textarea.style.left = "-9999px";
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    if (!document.execCommand("copy")) {
      throw new Error("clipboard_unavailable");
    }
  } finally {
    document.body.removeChild(textarea);
    activeElement?.focus();
  }
}

async function writeClipboard(value: string): Promise<void> {
  const clipboard = navigator.clipboard;
  if (clipboard?.writeText) {
    try {
      await clipboard.writeText(value);
      return;
    } catch {
      // Fall back for WebViews or permission-restricted contexts.
    }
  }
  copyWithExecCommand(value);
}

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const showStatus = useCallback((nextStatus: "copied" | "failed") => {
    setStatus(nextStatus);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setStatus("idle"), 1400);
  }, []);

  const handleCopy = useCallback(() => {
    void writeClipboard(value)
      .then(() => showStatus("copied"))
      .catch(() => showStatus("failed"));
  }, [showStatus, value]);

  const copied = status === "copied";
  const failed = status === "failed";
  const buttonLabel = copied ? "已复制" : failed ? "复制失败" : `复制${label}`;

  return (
    <button
      type="button"
      className={`copy-button${copied ? " copied" : ""}${failed ? " failed" : ""}`}
      onClick={handleCopy}
      title={buttonLabel}
      aria-label={buttonLabel}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
    </button>
  );
}
