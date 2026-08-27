import { screen, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";

import { expectCsrf, renderApp, server, user } from "./setup";

const previewResponse = {
  summary: {
    total: 3,
    valid: 2,
    warning: 1,
    error: 1,
  },
  items: [
    {
      row: 2,
      status: "valid",
      messages: [],
      draft: {
        title: "登录成功",
        module: "账号",
        tags: ["P0", "smoke"],
        content_markdown: "## 执行任务\n- 打开 App\n- 输入账号密码\n\n## 断言\n- 登录成功",
        automation_level: "auto",
      },
    },
    {
      row: 3,
      status: "error",
      messages: ["内容为空，需补充执行步骤"],
      draft: {
        title: "缺少标题",
        module: "支付",
        tags: ["P1"],
        content_markdown: " ",
        automation_level: "auto",
      },
    },
    {
      row: 4,
      status: "warning",
      messages: ["用例库中已有同名用例"],
      draft: {
        title: "登录成功",
        module: "账号",
        tags: ["P0"],
        content_markdown: "重复标题示例",
        automation_level: "auto",
      },
    },
  ],
};

it("renders the case import preview workflow", async () => {
  let previewCalls = 0;
  server.use(
    http.post("/api/v1/cases/import/preview", ({ request }) => {
      expectCsrf(request);
      previewCalls += 1;
      return HttpResponse.json(previewResponse);
    }),
  );

  renderApp("/cases/import/preview");

  expect(await screen.findByRole("heading", { name: "导入用例" })).toBeVisible();
  expect(screen.getByText("先解析并校验导入内容，确认无误后再批量写入用例库。"))
    .toBeVisible();
  expect(screen.getByRole("button", { name: "CSV 文件" })).toHaveClass("selected");
  expect(screen.getByLabelText("导入内容")).toHaveValue("");
  expect((screen.getByLabelText("导入内容") as HTMLTextAreaElement).placeholder)
    .toContain("title,module,tags,content_markdown");
  expect(previewCalls).toBe(0);
  expect(screen.getByText("0 条可导入")).toBeVisible();
  expect(screen.getByText("0 条需处理")).toBeVisible();

  await user.type(screen.getByLabelText("导入内容"), "title,module,tags,content_markdown");
  await user.click(screen.getByRole("button", { name: "重新解析" }));

  expect(await screen.findByText("2 条可导入")).toBeVisible();
  expect(screen.getByText("1 条需处理")).toBeVisible();

  const table = screen.getByRole("table", { name: "用例导入预览" });
  expect(within(table).getAllByText("登录成功")).toHaveLength(2);
  expect(within(table).getByText(/断言，登录成功/)).toBeVisible();
  expect(within(table).getByText("缺少标题")).toBeVisible();
  expect(within(table).getByText("疑似重复")).toBeVisible();
  expect(within(table).getByText("内容为空，需补充执行步骤")).toBeVisible();
  expect(screen.getByRole("button", { name: "确认导入 2 条" })).toBeDisabled();
});

it("links to the import preview from case library", async () => {
  server.use(
    http.get("/api/v1/cases", () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 })),
    http.get("/api/v1/cases/tags", () => HttpResponse.json({ items: [] })),
    http.get("/api/v1/cases/modules", () => HttpResponse.json({ items: [] })),
  );

  renderApp("/cases");

  expect(await screen.findByRole("link", { name: "导入用例" }))
    .toHaveAttribute("href", "/biz/biz_default/cases/import/preview");
});

it("imports parsed cases after a clean preview", async () => {
  let importedPayload: unknown = null;
  server.use(
    http.post("/api/v1/cases/import/preview", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        summary: { total: 1, valid: 1, warning: 0, error: 0 },
        items: [{
          row: 2,
          status: "valid",
          messages: [],
          draft: {
            title: "导入用例A",
            module: "账号",
            tags: ["P0"],
            content_markdown: "## 执行任务\n- 打开 App",
            automation_level: "auto",
          },
        }],
      });
    }),
    http.post("/api/v1/cases/import", async ({ request }) => {
      expectCsrf(request);
      importedPayload = await request.json();
      return HttpResponse.json({
        created_count: 1,
        items: [{
          id: "case_imported",
          title: "导入用例A",
          module: "账号",
          tags: ["P0"],
          content_markdown: "## 执行任务\n- 打开 App",
          automation_level: "auto",
          execution_count: 0,
          pass_count: 0,
          fail_count: 0,
          last_executed_at: null,
          created_by: "admin",
          created_at: "2026-07-30T00:00:00Z",
          updated_at: "2026-07-30T00:00:00Z",
        }],
      }, { status: 201 });
    }),
  );

  renderApp("/cases/import/preview");

  await user.type(await screen.findByLabelText("导入内容"), "title,module,tags,content_markdown");
  await user.click(screen.getByRole("button", { name: "重新解析" }));

  const importButton = await screen.findByRole("button", { name: "确认导入 1 条" });
  expect(importButton).toBeEnabled();
  await user.click(importButton);

  expect(await screen.findByRole("status")).toHaveTextContent("已成功导入 1 条用例");
  expect(importedPayload).toMatchObject({
    items: [expect.objectContaining({ title: "导入用例A" })],
  });
});

it("allows switching markdown and excel import formats", async () => {
  const formats: string[] = [];
  server.use(
    http.post("/api/v1/cases/import/preview", async ({ request }) => {
      expectCsrf(request);
      const body = await request.json() as { format: string };
      formats.push(body.format);
      return HttpResponse.json({
        summary: { total: 0, valid: 0, warning: 0, error: 0 },
        items: [],
      });
    }),
  );

  renderApp("/cases/import/preview");

  const markdown = await screen.findByRole("button", { name: "Markdown" });
  const excel = screen.getByRole("button", { name: "Excel" });
  expect(markdown).toBeEnabled();
  expect(excel).toBeEnabled();

  await user.click(markdown);
  expect(markdown).toHaveClass("selected");
  expect((screen.getByLabelText("导入内容") as HTMLTextAreaElement).value)
    .toBe("");
  expect((screen.getByLabelText("导入内容") as HTMLTextAreaElement).placeholder)
    .toContain("title:");

  await user.click(excel);
  expect(excel).toHaveClass("selected");
  expect((screen.getByLabelText("导入内容") as HTMLTextAreaElement).value)
    .toBe("");
  expect((screen.getByLabelText("导入内容") as HTMLTextAreaElement).placeholder)
    .toContain("title\tmodule");

  expect(formats).toEqual([]);
});

it("removes preview rows before confirming import", async () => {
  server.use(
    http.post("/api/v1/cases/import/preview", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        summary: { total: 2, valid: 2, warning: 0, error: 0 },
        items: [
          {
            row: 2,
            status: "valid",
            messages: [],
            draft: {
              title: "保留用例",
              module: "账号",
              tags: ["P0"],
              content_markdown: "## 执行任务\n- 打开 App",
              automation_level: "auto",
            },
          },
          {
            row: 3,
            status: "valid",
            messages: [],
            draft: {
              title: "删除用例",
              module: "支付",
              tags: ["P1"],
              content_markdown: "## 执行任务\n- 提交订单",
              automation_level: "auto",
            },
          },
        ],
      });
    }),
  );

  renderApp("/cases/import/preview");

  await user.type(await screen.findByLabelText("导入内容"), "title,module,tags,content_markdown");
  await user.click(screen.getByRole("button", { name: "重新解析" }));

  expect(await screen.findByText("保留用例")).toBeVisible();
  expect(screen.getByText("删除用例")).toBeVisible();
  expect(screen.getByRole("button", { name: "确认导入 2 条" })).toBeEnabled();

  const table = screen.getByRole("table", { name: "用例导入预览" });
  const initialRows = within(table).getAllByRole("row").slice(1);
  expect(within(initialRows[0]).getAllByRole("cell")[0]).toHaveTextContent("1");
  expect(within(initialRows[1]).getAllByRole("cell")[0]).toHaveTextContent("2");

  await user.click(screen.getByRole("button", { name: "移除 删除用例" }));

  expect(screen.queryByText("删除用例")).not.toBeInTheDocument();
  expect(screen.getByText("1 条可导入")).toBeVisible();
  expect(screen.getByRole("button", { name: "确认导入 1 条" })).toBeEnabled();
});

it("keeps preview display numbers starting from one after row removal", async () => {
  server.use(
    http.post("/api/v1/cases/import/preview", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        summary: { total: 2, valid: 2, warning: 0, error: 0 },
        items: [
          {
            row: 3,
            status: "valid",
            messages: [],
            draft: {
              title: "支付下单成功",
              module: "支付",
              tags: ["P1"],
              content_markdown: "## 执行任务\n- 选择商品",
              automation_level: "auto",
            },
          },
          {
            row: 4,
            status: "valid",
            messages: [],
            draft: {
              title: "搜索无结果",
              module: "搜索",
              tags: ["P2"],
              content_markdown: "## 执行任务\n- 打开搜索页",
              automation_level: "auto",
            },
          },
        ],
      });
    }),
  );

  renderApp("/cases/import/preview");

  await user.type(await screen.findByLabelText("导入内容"), "title,module,tags,content_markdown");
  await user.click(screen.getByRole("button", { name: "重新解析" }));

  const table = await screen.findByRole("table", { name: "用例导入预览" });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent("1");
  expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent("2");

  await user.click(screen.getByRole("button", { name: "移除 支付下单成功" }));

  const remainingRows = within(table).getAllByRole("row").slice(1);
  expect(within(remainingRows[0]).getAllByRole("cell")[0]).toHaveTextContent("1");
  expect(within(remainingRows[0]).getByText("搜索无结果")).toBeVisible();
});

it("previews a selected import file", async () => {
  let uploadedFileName = "";
  let requestedFormat = "";
  server.use(
    http.post("/api/v1/cases/import/preview", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        summary: { total: 0, valid: 0, warning: 0, error: 0 },
        items: [],
      });
    }),
    http.post("/api/v1/cases/import/file/preview", async ({ request }) => {
      expectCsrf(request);
      uploadedFileName = decodeURIComponent(request.headers.get("X-File-Name") ?? "");
      requestedFormat = new URL(request.url).searchParams.get("format") ?? "";
      return HttpResponse.json({
        summary: { total: 1, valid: 1, warning: 0, error: 0 },
        items: [{
          row: 2,
          status: "valid",
          messages: [],
          draft: {
            title: "文件导入用例",
            module: "账号",
            tags: ["P0"],
            content_markdown: "## 执行任务\n- 打开 App",
            automation_level: "auto",
          },
        }],
      });
    }),
  );

  renderApp("/cases/import/preview");

  const input = await screen.findByLabelText("选择导入文件");
  await user.upload(
    input,
    new File(
      ["title,module,tags,content_markdown\n文件导入用例,账号,P0,内容"],
      "cases.csv",
      { type: "text/csv" },
    ),
  );

  expect(await screen.findByText("cases.csv")).toBeVisible();
  expect(await screen.findByText("文件导入用例")).toBeVisible();
  expect(uploadedFileName).toBe("cases.csv");
  expect(requestedFormat).toBe("auto");
});

it("removes the selected import file without clearing pasted content", async () => {
  server.use(
    http.post("/api/v1/cases/import/file/preview", ({ request }) => {
      expectCsrf(request);
      return HttpResponse.json({
        summary: { total: 1, valid: 1, warning: 0, error: 0 },
        items: [{
          row: 2,
          status: "valid",
          messages: [],
          draft: {
            title: "文件导入用例",
            module: "账号",
            tags: ["P0"],
            content_markdown: "## 执行任务\n- 打开 App",
            automation_level: "auto",
          },
        }],
      });
    }),
  );

  renderApp("/cases/import/preview");

  const textarea = await screen.findByLabelText("导入内容");
  await user.type(textarea, "title,module,tags,content_markdown");

  const input = screen.getByLabelText("选择导入文件") as HTMLInputElement;
  await user.upload(
    input,
    new File(
      ["title,module,tags,content_markdown\n文件导入用例,账号,P0,内容"],
      "cases.csv",
      { type: "text/csv" },
    ),
  );

  expect(await screen.findByText("cases.csv")).toBeVisible();
  expect(await screen.findByText("文件导入用例")).toBeVisible();
  expect(screen.getByRole("button", { name: "确认导入 1 条" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "移除当前导入文件" })).toHaveTextContent("×");

  await user.click(screen.getByRole("button", { name: "移除当前导入文件" }));

  expect(screen.queryByText("cases.csv")).not.toBeInTheDocument();
  expect(screen.queryByText("文件导入用例")).not.toBeInTheDocument();
  expect(input.files).toHaveLength(0);
  expect(textarea).toHaveValue("title,module,tags,content_markdown");
  expect(screen.getByText("0 条")).toBeVisible();
  expect(screen.getByText("0 条可导入")).toBeVisible();
  expect(screen.getByText("0 条需处理")).toBeVisible();
  expect(screen.getByRole("button", { name: "确认导入 0 条" })).toBeDisabled();
});
