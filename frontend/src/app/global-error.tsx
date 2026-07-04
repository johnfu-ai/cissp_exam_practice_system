"use client";

/**
 * Global error boundary (Next.js convention) — the last-resort catch that
 * replaces the <html>/<body> when even the root layout fails to render. Kept
 * dependency-free (no i18n/provider, no shadcn) because it sits ABOVE the root
 * layout. Hardcoded English is acceptable for this terminal boundary.
 */
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          padding: "2rem",
          textAlign: "center",
          color: "#1d1d1f",
        }}
      >
        <h2>Something went wrong</h2>
        <p style={{ color: "#6e6e73" }}>An unexpected error occurred.</p>
        <button
          type="button"
          onClick={() => reset()}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1.25rem",
            borderRadius: "9999px",
            border: "1px solid #d2d2d7",
            background: "#007aff",
            color: "#fff",
            fontSize: "0.95rem",
          }}
        >
          Retry
        </button>
      </body>
    </html>
  );
}
