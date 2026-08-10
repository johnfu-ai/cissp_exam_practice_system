import { describe, it, expect } from "vitest";
import {
  autoMapHeaders,
  buildImportTemplateCsv,
  parseCsvHeaders,
  remapCsv,
  REQUIRED_IMPORT_FIELDS,
} from "@/lib/import-template";

describe("import template (FR-IMP-03/04)", () => {
  it("builds a CSV with required canonical headers", () => {
    const csv = buildImportTemplateCsv();
    const headers = parseCsvHeaders(csv);
    for (const f of REQUIRED_IMPORT_FIELDS) {
      expect(headers).toContain(f);
    }
  });

  it("auto-maps case-insensitive headers", () => {
    const mapping = autoMapHeaders(["Question_Text", "domain", "unknown_col"]);
    expect(mapping["Question_Text"]).toBe("question_text");
    expect(mapping.domain).toBe("domain");
    expect(mapping.unknown_col).toBe("");
  });

  it("remaps CSV columns to canonical headers", () => {
    const src = "Stem,Type,A,B,Ans,Why,Dom\nQ?,single_choice,x,y,A,because,1\n";
    const mapping = {
      Stem: "question_text" as const,
      Type: "question_type" as const,
      A: "option_a" as const,
      B: "option_b" as const,
      Ans: "correct_answers" as const,
      Why: "explanation" as const,
      Dom: "domain" as const,
    };
    const out = remapCsv(src, mapping);
    const headers = parseCsvHeaders(out);
    expect(headers).toEqual([
      "question_text",
      "question_type",
      "option_a",
      "option_b",
      "correct_answers",
      "explanation",
      "domain",
    ]);
    expect(out).toContain("Q?");
  });
});
