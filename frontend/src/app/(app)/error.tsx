"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";

/**
 * Route-level error boundary for the authenticated app shell (audit P1 #29).
 * Catches render-time errors so a bad API response shape / null deref shows a
 * recoverable error card with a retry button instead of a blank screen.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error(error);
  }, [error]);
  return (
    <div className="mx-auto max-w-md p-8 text-center">
      <h2 className="text-lg font-semibold">{t("error.title")}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{t("error.description")}</p>
      <Button className="mt-4" size="pill" onClick={() => reset()}>
        {t("error.retry")}
      </Button>
    </div>
  );
}
