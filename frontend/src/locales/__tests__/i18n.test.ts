import { describe, it, expect } from "vitest";
import { en } from "../en";
import { zh } from "../zh";
import { makeT } from "../t";

describe("i18n dictionaries", () => {
  it("zh has every key en has", () => {
    const missing = keys(en).filter((k) => get(zh, k) === undefined);
    expect(missing).toEqual([]);
  });

  it("en has every key zh has (parity is bidirectional)", () => {
    // #33: the old test was one-directional (zh ⊆ en). A stale en key or a zh-only
    // key both indicate drift; enforce symmetry.
    const missing = keys(zh).filter((k) => get(en, k) === undefined);
    expect(missing).toEqual([]);
  });

  it("every zh leaf is a non-empty string (no blank/placeholder translations)", () => {
    // #33: a zh key that exists but is "" is silently broken (UI shows nothing).
    const blanks = keys(zh).filter((k) => {
      const v = get(zh, k);
      return typeof v !== "string" || v.length === 0;
    });
    expect(blanks).toEqual([]);
  });

  it("zh is not a wholesale copy of en (translations actually differ)", () => {
    // #33: guard against a copy-paste en->zh that leaves Chinese users seeing
    // English. At least one leaf must differ.
    const enLeaves = keys(en).map((k) => String(get(en, k)));
    const zhLeaves = keys(zh).map((k) => String(get(zh, k)));
    const identical = enLeaves.every((v, i) => v === zhLeaves[i]);
    expect(identical).toBe(false);
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
