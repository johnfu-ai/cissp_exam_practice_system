import { describe, it, expect } from "vitest";
import { en } from "../en";
import { zh } from "../zh";
import { makeT } from "../t";

describe("i18n dictionaries", () => {
  it("zh has every key en has", () => {
    const missing = keys(en).filter((k) => get(zh, k) === undefined);
    expect(missing).toEqual([]);
  });

  it("t returns the en value for a known key", () => {
    const t = makeT(en);
    expect(t("common.save")).toBe("Save");
  });

  it("t interpolates {vars}", () => {
    const t = makeT(en);
    expect(t("common.ofN", { n: 5 })).toBe("of 5");
  });

  it("t falls back to the key when missing", () => {
    const t = makeT(en);
    expect(t("nope.does.not.exist")).toBe("nope.does.not.exist");
  });

  it("zh translates a known key", () => {
    const t = makeT(zh);
    expect(t("common.save")).toBe("保存");
  });
});

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}
function get(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => {
    if (o && typeof o === "object") {
      return (o as Record<string, unknown>)[k];
    }
    return undefined;
  }, obj);
}
