"use client";

import { useT } from "@/lib/i18n/provider";

/**
 * Persistent legal disclaimers (PRD §7.5 NFR-COMP-03/04): trademark attribution
 * + "not an official ISC2 platform" statement. Rendered in the app + auth shells
 * so it appears on every page.
 */
export function LegalFooter() {
  const t = useT();
  return (
    <footer
      role="contentinfo"
      className="mt-8 border-t pt-4 text-center text-xs text-muted-foreground space-y-1"
    >
      <p>{t("legal.trademark")}</p>
      <p>{t("legal.notOfficial")}</p>
    </footer>
  );
}
