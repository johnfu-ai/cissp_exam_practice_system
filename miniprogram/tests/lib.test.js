import { beforeEach, describe, expect, it } from "vitest";
import { installWxMock } from "./wx-mock";

let wx;

beforeEach(() => {
  wx = installWxMock();
  for (const key of Object.keys(require.cache)) {
    if (key.includes("/miniprogram/lib/")) delete require.cache[key];
  }
});

describe("answer sheet", () => {
  const sheet = require("../lib/answer-sheet.js");

  it("statuses match the web implementation", () => {
    const s = sheet.emptySheet();
    expect(sheet.cellStatus(s, 0)).toBe("unanswered");
    s.answered[0] = true;
    s.wrong[1] = true;
    s.flagged[2] = true;
    expect(sheet.cellStatus(s, 0)).toBe("answered");
    expect(sheet.cellStatus(s, 1)).toBe("wrong");
    expect(sheet.cellStatus(s, 2)).toBe("flagged");
    expect(sheet.sheetCounts(s, 3)).toEqual({
      answered: 1,
      wrong: 1,
      unanswered: 0,
      flagged: 1,
    });
  });

  it("clock formatting matches the web player", () => {
    expect(sheet.formatClock(0)).toBe("00:00");
    expect(sheet.formatClock(65_000)).toBe("01:05");
    expect(sheet.formatClock(3_600_000)).toBe("1:00:00");
    expect(sheet.remainingMs(1000, 1500)).toBe(0);
  });
});

describe("i18n", () => {
  it("defaults to zh and interpolates vars", () => {
    const i18n = require("../lib/i18n.js");
    i18n.init();
    expect(i18n.getLocale()).toBe("zh");
    expect(i18n.t("wrongNTimes", { count: 3 })).toBe("错误 3 次");
  });

  it("switches locale persistently and en/zh keys stay in parity", () => {
    const i18n = require("../lib/i18n.js");
    i18n.setLocale("en");
    expect(i18n.t("startPractice")).toBe("Practice");
    expect(wx.__store.get("cissp_locale")).toBe("en");
    expect(Object.keys(i18n.DICTS.en).sort()).toEqual(Object.keys(i18n.DICTS.zh).sort());
  });
});

describe("papers api surface", () => {
  it("papers hooks hit the documented endpoints", async () => {
    wx.__respond({ statusCode: 200, data: { items: [], total: 0 }, header: {} });
    const papers = require("../lib/papers.js");
    await papers.listPapers();
    expect(wx.__calls.request[0].url).toContain("/api/papers");
    expect(wx.__calls.request[0].method).toBe("GET");
  });
});
