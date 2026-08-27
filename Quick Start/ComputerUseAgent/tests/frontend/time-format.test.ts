import { describe, expect, it } from "vitest";

import {
  formatChinaDate,
  formatChinaDateTime,
  formatDurationSeconds,
  formatElapsedTime,
  formatTaskElapsedTime,
} from "../../web/utils/time";

describe("China time formatting", () => {
  it("formats UTC timestamps as Asia Shanghai date time", () => {
    expect(formatChinaDateTime("2026-07-28T03:35:31Z")).toBe("2026-07-28 11:35:31");
  });

  it("formats UTC timestamps as Asia Shanghai date", () => {
    expect(formatChinaDate("2026-07-28T16:35:31Z")).toBe("2026-07-29");
  });

  it("treats timezone-less timestamps as UTC", () => {
    expect(formatChinaDateTime("2026-07-28T05:27:01")).toBe("2026-07-28 13:27:01");
    expect(formatChinaDateTime("2026-07-28 05:27:01")).toBe("2026-07-28 13:27:01");
  });

  it("returns dash for empty or invalid dates", () => {
    expect(formatChinaDateTime(null)).toBe("-");
    expect(formatChinaDateTime("not-a-date")).toBe("-");
  });

  it("formats duration seconds as compact Chinese text", () => {
    expect(formatDurationSeconds(0)).toBe("0 秒");
    expect(formatDurationSeconds(65)).toBe("1 分 5 秒");
    expect(formatDurationSeconds(3661)).toBe("1 小时 01 分 01 秒");
    expect(formatDurationSeconds(null)).toBe("-");
    expect(formatDurationSeconds(-1)).toBe("-");
  });

  it("formats elapsed time from start to end", () => {
    expect(formatElapsedTime("2026-07-28T03:35:31Z", "2026-07-28T03:38:32Z")).toBe("3 分 1 秒");
  });

  it("formats running elapsed time with supplied now", () => {
    expect(formatElapsedTime("2026-07-28T03:35:31Z", null, Date.parse("2026-07-28T04:36:32Z"))).toBe("1 小时 01 分 01 秒");
  });

  it("keeps queued task elapsed time at zero", () => {
    expect(formatTaskElapsedTime(
      "queued",
      "2026-07-28T03:35:31Z",
      null,
      Date.parse("2026-07-28T04:36:32Z"),
    )).toBe("0 秒");
  });

  it("keeps not-started non-queued task elapsed time blank", () => {
    expect(formatTaskElapsedTime("running", null, null)).toBe("-");
  });
});
