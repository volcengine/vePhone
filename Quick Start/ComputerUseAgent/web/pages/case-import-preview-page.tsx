import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import type {
  CaseImportConfirmResponse,
  CaseImportFormat,
  CaseImportPreviewItem,
  CaseImportPreviewResponse,
} from "../api/types";
import { BusinessLink as Link } from "../components/business-link";
import { PageHeader } from "../components/page-header";

const sampleCsv = `title,module,tags,content_markdown
登录成功,账号,"P0,smoke","## 执行任务
- 打开 App
- 输入账号密码

## 断言
- 登录成功"`;

const sampleMarkdown = `---
title: 登录成功
module: 账号
tags: [P0, smoke]
---

## 执行任务
- 打开 App
- 输入账号密码

## 断言
- 登录成功`;

const sampleExcel = `title\tmodule\ttags\tcontent_markdown
登录成功\t账号\tP0,smoke\t## 执行任务\\n- 打开 App\\n- 输入账号密码`;

const FORMAT_OPTIONS: Array<{ value: CaseImportFormat; label: string; sample: string }> = [
  { value: "csv", label: "CSV 文件", sample: sampleCsv },
  { value: "markdown", label: "Markdown", sample: sampleMarkdown },
  { value: "excel", label: "Excel", sample: sampleExcel },
];

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 16V4m0 0 4 4m-4-4-4 4M4 20h16" />
    </svg>
  );
}

function statusLabel(status: CaseImportPreviewItem["status"]): string {
  if (status === "valid") return "可导入";
  if (status === "warning") return "疑似重复";
  return "需处理";
}

function summaryText(item: CaseImportPreviewItem): string {
  const lines = item.draft.content_markdown
    .split(/\r?\n/)
    .map((line) => line.replace(/^#+\s*/, "").replace(/^-\s*/, "").trim())
    .filter(Boolean);
  return lines.join("，") || "内容为空";
}

function friendlyImportError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "导入用例失败，请稍后重试。";
}

function readFileAsArrayBuffer(file: File): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      if (reader.result instanceof ArrayBuffer) {
        resolve(reader.result);
        return;
      }
      if (typeof reader.result === "string") {
        resolve(new TextEncoder().encode(reader.result).buffer);
        return;
      }
      reject(new Error("case_import_file_read_failed"));
    });
    reader.addEventListener("error", () => reject(reader.error));
    reader.readAsArrayBuffer(file);
  });
}

export function CaseImportPreviewPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [format, setFormat] = useState<CaseImportFormat>("csv");
  const [content, setContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewRows, setPreviewRows] = useState<CaseImportPreviewItem[]>([]);
  const [importResult, setImportResult] =
    useState<CaseImportConfirmResponse | null>(null);
  const selectedFormat = FORMAT_OPTIONS.find((item) => item.value === format) ?? FORMAT_OPTIONS[0];

  const previewImport = useMutation({
    mutationFn: (payload: { format: CaseImportFormat; content: string }) =>
      api.post<CaseImportPreviewResponse>("/cases/import/preview", {
        format: payload.format,
        content: payload.content,
      }),
    onSuccess: (data) => {
      setPreviewRows(data.items);
      setImportResult(null);
    },
  });

  const confirmImport = useMutation({
    mutationFn: (items: CaseImportPreviewItem[]) =>
      api.post<CaseImportConfirmResponse>("/cases/import", {
        items: items.map((item) => item.draft),
      }),
    onSuccess: (data) => {
      setImportResult(data);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["case-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["case-tags"] });
      void queryClient.invalidateQueries({ queryKey: ["case-modules"] });
    },
  });

  const previewFileImport = useMutation({
    mutationFn: async (file: File) =>
      api.postRaw<CaseImportPreviewResponse>(
        "/cases/import/file/preview?format=auto",
        await readFileAsArrayBuffer(file),
        {
          "Content-Type": "application/octet-stream",
          "X-File-Name": encodeURIComponent(file.name),
        },
      ),
    onSuccess: (data) => {
      setPreviewRows(data.items);
      setImportResult(null);
    },
  });

  function switchFormat(nextFormat: CaseImportFormat) {
    const option = FORMAT_OPTIONS.find((item) => item.value === nextFormat);
    if (!option) return;
    setFormat(nextFormat);
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setImportResult(null);
  }

  function previewSelectedFile(file: File) {
    setSelectedFile(file);
    previewFileImport.mutate(file);
  }

  function removeSelectedFile() {
    setSelectedFile(null);
    setPreviewRows([]);
    setImportResult(null);
    previewFileImport.reset();
    confirmImport.reset();
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removePreviewRow(rowToRemove: CaseImportPreviewItem) {
    setPreviewRows((currentRows) =>
      currentRows.filter((row) => row !== rowToRemove),
    );
    setImportResult(null);
  }

  const rows = previewRows;
  const summary = useMemo(
    () => ({
      total: rows.length,
      valid: rows.filter((row) => row.status !== "error").length,
      error: rows.filter((row) => row.status === "error").length,
    }),
    [rows],
  );
  const importableRows = useMemo(
    () => rows.filter((row) => row.status !== "error"),
    [rows],
  );
  const hasErrors = summary.error > 0;

  return (
    <div className="page-container case-import-preview-page">
      <PageHeader
        breadcrumbs={[
          { label: "首页", to: "/tasks" },
          { label: "用例库", to: "/cases" },
          { label: "导入用例" },
        ]}
        title="导入用例"
        description="先解析并校验导入内容，确认无误后再批量写入用例库。"
        actions={
          <Link to="/cases" className="secondary-button">
            返回用例库
          </Link>
        }
      />

      <div className="case-import-layout">
        <section className="case-import-panel">
          <div className="case-import-section-heading">
            <span className="section-kicker">导入源</span>
            <h2>选择格式并粘贴内容</h2>
          </div>
          <div className="case-import-format-tabs" aria-label="导入格式">
            {FORMAT_OPTIONS.map((option) => (
              <button
                type="button"
                className={format === option.value ? "selected" : ""}
                key={option.value}
                onClick={() => switchFormat(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <label className="case-import-file-drop">
            <input
              ref={fileInputRef}
              aria-label="选择导入文件"
              type="file"
              accept=".csv,.md,.markdown,.tsv,.xls,.xlsx"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) previewSelectedFile(file);
              }}
            />
            <span>拖拽文件到这里，或点击选择文件</span>
            <small>支持 CSV / Markdown / Excel，单次最多 100 条用例</small>
          </label>
          {selectedFile && (
            <div className="case-import-selected-file">
              <span>{selectedFile.name}</span>
              <small>{Math.ceil(selectedFile.size / 1024)} KB</small>
              <button
                type="button"
                aria-label="移除当前导入文件"
                onClick={removeSelectedFile}
              >
                ×
              </button>
            </div>
          )}
          <label className="case-import-textarea">
            <span>导入内容</span>
            <textarea
              aria-label="导入内容"
              placeholder={selectedFormat.sample}
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          {(previewImport.isError || previewFileImport.isError || confirmImport.isError) && (
            <p className="wizard-error" role="alert">
              {friendlyImportError(
                previewImport.error ?? previewFileImport.error ?? confirmImport.error,
              )}
            </p>
          )}
          {importResult && (
            <p className="case-import-success" role="status">
              已成功导入 {importResult.created_count} 条用例。
            </p>
          )}
          <div className="case-import-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={previewImport.isPending || previewFileImport.isPending}
              onClick={() => previewImport.mutate({ format, content })}
            >
              {previewImport.isPending || previewFileImport.isPending ? "解析中…" : "重新解析"}
            </button>
            <button
              type="button"
              className="primary-button"
              disabled={
                hasErrors
                || importableRows.length === 0
                || previewImport.isPending
                || previewFileImport.isPending
                || confirmImport.isPending
              }
              onClick={() => confirmImport.mutate(importableRows)}
            >
              <UploadIcon />
              {confirmImport.isPending
                ? "导入中…"
                : `确认导入 ${importableRows.length} 条`}
            </button>
          </div>
        </section>

        <aside className="case-import-summary">
          <div>
            <span>解析结果</span>
            <strong>{summary.total} 条</strong>
          </div>
          <div>
            <span>可导入</span>
            <strong>{summary.valid} 条可导入</strong>
          </div>
          <div>
            <span>需处理</span>
            <strong>{summary.error} 条需处理</strong>
          </div>
          <p>存在错误项时，确认导入按钮保持禁用。可移除错误项或补全字段后再导入。</p>
        </aside>
      </div>

      <section className="case-import-preview-card">
        <div className="case-import-section-heading">
          <span className="section-kicker">预览校验</span>
          <h2>确认将导入的用例</h2>
        </div>
        <div className="table-scroll">
          <table className="data-table case-import-table" aria-label="用例导入预览">
            <thead>
              <tr>
                <th>序号</th>
                <th>用例名称</th>
                <th>模块</th>
                <th>标签</th>
                <th>内容摘要</th>
                <th>校验状态</th>
                <th>说明</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const summary = summaryText(row);
                return (
                  <tr key={`${row.row}-${row.draft.title}`}>
                    <td>{index + 1}</td>
                    <td>{row.draft.title}</td>
                    <td>{row.draft.module ?? "-"}</td>
                    <td>
                      <div className="tag-list">
                        {(row.draft.tags ?? []).map((tag) => (
                          <span className="tag tag-primary" key={tag}>{tag}</span>
                        ))}
                      </div>
                    </td>
                    <td className="case-import-summary-cell" title={summary}>{summary}</td>
                    <td>
                      <span className={`case-import-status ${row.status === "valid" ? "success" : row.status === "warning" ? "warning" : "danger"}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td>{row.messages.length > 0 ? row.messages.join("；") : "-"}</td>
                    <td>
                      <button
                        type="button"
                        aria-label={`移除 ${row.draft.title || `第 ${row.row} 行`}`}
                        className="case-import-remove-button"
                        onClick={() => removePreviewRow(row)}
                      >
                        移除
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
