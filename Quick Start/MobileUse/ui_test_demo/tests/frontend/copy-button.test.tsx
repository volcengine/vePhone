import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { CopyButton } from "../../web/components/copy-button";
import { user } from "./setup";

afterEach(() => {
  vi.restoreAllMocks();
});

it("falls back to execCommand when async clipboard fails", async () => {
  const writeText = vi.fn().mockRejectedValue(new Error("denied"));
  const execCommand = vi.fn(() => true);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: execCommand,
  });

  render(<CopyButton value={"## 执行任务\n打开首页"} label="用例内容" />);

  await user.click(screen.getByRole("button", { name: "复制用例内容" }));

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "已复制" })).toBeVisible(),
  );
  expect(writeText).toHaveBeenCalledWith("## 执行任务\n打开首页");
  expect(execCommand).toHaveBeenCalledWith("copy");
});
