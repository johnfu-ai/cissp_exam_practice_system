import type { LanguageCode } from "@/lib/api/types";

/** P3: deduped badge label for a question's available languages (was copied
 *  in both list.tsx and detail.tsx). */
export function langBadge(languages: LanguageCode[]): string {
  const hasEn = languages.includes("en");
  const hasZh = languages.includes("zh");
  if (hasEn && hasZh) return "EN+中";
  if (hasZh) return "中";
  if (hasEn) return "EN";
  return "-";
}
