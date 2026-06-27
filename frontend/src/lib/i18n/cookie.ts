import type { Locale } from "./types";

export const UI_LANG_COOKIE = "ui_lang";
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/** Read the UI-language cookie client-side. Defaults to "en". */
export function readUiLangCookie(): Locale {
  if (typeof document === "undefined") return "en";
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${UI_LANG_COOKIE}=`));
  return match?.split("=")[1] === "zh" ? "zh" : "en";
}

/** Write the UI-language cookie so the next SSR render picks the right locale. */
export function writeUiLangCookie(locale: Locale): void {
  if (typeof document === "undefined") return;
  document.cookie = `${UI_LANG_COOKIE}=${locale}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
}
