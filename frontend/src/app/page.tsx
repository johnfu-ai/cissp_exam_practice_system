const BACKEND_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

type Health = { status: string; db: string; redis: string };

async function fetchHealth(): Promise<Health | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}

function statusColor(value: string): string {
  return value === "ok" || value === "healthy"
    ? "text-green-600 dark:text-green-400"
    : "text-red-600 dark:text-red-400";
}

export default async function Home() {
  const health = await fetchHealth();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-xl space-y-6 text-center">
        <h1 className="text-4xl font-bold tracking-tight">CISSP Exam Practice</h1>
        <p className="text-neutral-600 dark:text-neutral-400">
          Foundations &amp; data model sub-project. Backend service status:
        </p>
        {health === null ? (
          <p className="text-red-600 dark:text-red-400">
            Backend unreachable at <code>{BACKEND_URL}</code>
          </p>
        ) : (
          <dl className="inline-block space-y-2 text-left">
            <div className="flex justify-between gap-8">
              <dt className="font-medium">Overall</dt>
              <dd className={statusColor(health.status)}>{health.status}</dd>
            </div>
            <div className="flex justify-between gap-8">
              <dt className="font-medium">Database</dt>
              <dd className={statusColor(health.db)}>{health.db}</dd>
            </div>
            <div className="flex justify-between gap-8">
              <dt className="font-medium">Redis</dt>
              <dd className={statusColor(health.redis)}>{health.redis}</dd>
            </div>
          </dl>
        )}
      </div>
    </main>
  );
}
