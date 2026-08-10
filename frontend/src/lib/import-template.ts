/** PRD §10.1 canonical CSV columns for FR-IMP-03/04. */

export const CANONICAL_IMPORT_FIELDS = [
  "question_text",
  "question_type",
  "option_a",
  "option_b",
  "option_c",
  "option_d",
  "correct_answers",
  "explanation",
  "option_explanations",
  "domain",
  "knowledge_points",
  "book",
  "chapter",
  "difficulty",
  "tags",
  "source",
  "license_status",
  "language",
  "question_text_zh",
  "option_a_zh",
  "option_b_zh",
  "option_c_zh",
  "option_d_zh",
  "explanation_zh",
  "option_explanations_zh",
] as const;

export type CanonicalImportField = (typeof CANONICAL_IMPORT_FIELDS)[number];

export const REQUIRED_IMPORT_FIELDS: CanonicalImportField[] = [
  "question_text",
  "question_type",
  "option_a",
  "option_b",
  "correct_answers",
  "explanation",
  "domain",
];

const TEMPLATE_SAMPLE = [
  "Which security principle ensures data is not altered?",
  "single_choice",
  "Confidentiality",
  "Integrity",
  "Availability",
  "Accountability",
  "B",
  "Integrity protects against unauthorized modification.",
  "",
  "1",
  "integrity",
  "OSG 10th Edition",
  "Chapter 1",
  "medium",
  "governance",
  "user_import",
  "user_owned",
  "en",
  "哪项安全原则确保数据不被篡改？",
  "保密性",
  "完整性",
  "可用性",
  "可问责性",
  "完整性防止未授权修改。",
  "",
];

export function buildImportTemplateCsv(): string {
  const header = CANONICAL_IMPORT_FIELDS.join(",");
  const row = TEMPLATE_SAMPLE.map(csvEscape).join(",");
  return `${header}\n${row}\n`;
}

function csvEscape(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

/** Parse the first CSV line into headers (simple, quote-aware). */
export function parseCsvHeaders(text: string): string[] {
  const line = text.split(/\r?\n/).find((l) => l.trim().length > 0) ?? "";
  const cells: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      cells.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  cells.push(cur.trim());
  return cells.filter(Boolean);
}

export function autoMapHeaders(headers: string[]): Record<string, CanonicalImportField | ""> {
  const lowerCanon = new Map(
    CANONICAL_IMPORT_FIELDS.map((f) => [f.toLowerCase(), f]),
  );
  const mapping: Record<string, CanonicalImportField | ""> = {};
  for (const h of headers) {
    mapping[h] = lowerCanon.get(h.trim().toLowerCase()) ?? "";
  }
  return mapping;
}

/** Rewrite a CSV so headers become canonical fields per [mapping]. */
export function remapCsv(text: string, mapping: Record<string, CanonicalImportField | "">): string {
  const lines = text.split(/\r?\n/).filter((l, idx) => !(idx > 0 && l.trim() === "" && idx === text.split(/\r?\n/).length - 1));
  if (lines.length === 0) return text;
  const headers = parseCsvHeaders(lines[0]);
  const targets = headers.map((h) => mapping[h] || "");
  const used = targets.filter(Boolean);
  if (used.length === 0) return text;

  const outHeader = used.join(",");
  const outRows: string[] = [outHeader];

  for (let r = 1; r < lines.length; r++) {
    if (!lines[r].trim()) continue;
    const cells = parseCsvRow(lines[r]);
    const mapped: string[] = [];
    for (let i = 0; i < headers.length; i++) {
      if (!targets[i]) continue;
      mapped.push(csvEscape(cells[i] ?? ""));
    }
    outRows.push(mapped.join(","));
  }
  return outRows.join("\n") + "\n";
}

function parseCsvRow(line: string): string[] {
  const cells: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      cells.push(cur);
      cur = "";
      continue;
    }
    cur += ch;
  }
  cells.push(cur);
  return cells;
}

export function downloadTextFile(filename: string, content: string, mime = "text/csv;charset=utf-8") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
