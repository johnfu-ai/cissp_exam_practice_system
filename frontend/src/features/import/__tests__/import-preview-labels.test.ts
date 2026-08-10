import { describe, expect, it } from "vitest";
import { en } from "@/locales/en";
import { makeT } from "@/locales/t";

describe("import preview summary labels", () => {
  it("exposes duplicates and conflicts locale keys", () => {
    const t = makeT(en);
    expect(t("importWiz.duplicates")).toBe("Duplicates");
    expect(t("importWiz.conflicts", { n: 2 })).toContain("2");
    expect(t("importWiz.paste")).toBeTruthy();
  });
});
