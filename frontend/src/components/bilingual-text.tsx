"use client";

import type { LanguageMode } from "@/lib/api/types";

/**
 * Render text according to the user's language mode.
 *
 * - `en`   → English only
 * - `zh`   → Chinese only
 * - `bilingual` → English stacked above Chinese (Chinese muted)
 *
 * When the requested language is null, fall back to the other language so the
 * slot is never empty.
 */
export function BilingualText({
  mode,
  en,
  zh,
  className,
}: {
  mode: LanguageMode;
  en: string | null;
  zh: string | null;
  className?: string;
}) {
  const showEn = mode !== "zh" && (en ?? zh) !== null;
  const showZh = mode !== "en" && (zh ?? en) !== null;
  return (
    <div className={className}>
      {showEn && <div className="en">{en ?? zh}</div>}
      {showZh && <div className="zh text-muted-foreground">{zh ?? en}</div>}
    </div>
  );
}

/**
 * Flatten a `Localized` value into a single string for the given mode.
 *
 * - `en` / `zh` → that language, falling back to the other when null
 * - `bilingual` → `"en  /  zh"` (omitting any null side)
 */
export function localizedText(
  mode: LanguageMode,
  loc: { en: string | null; zh: string | null },
): string {
  if (mode === "en") return loc.en ?? loc.zh ?? "";
  if (mode === "zh") return loc.zh ?? loc.en ?? "";
  const parts = [loc.en, loc.zh].filter((x): x is string => !!x);
  return parts.join("  /  ");
}
