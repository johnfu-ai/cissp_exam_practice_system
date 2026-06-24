"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";

const DEV_ADMIN_EMAIL = "admin@example.com";
const DEV_ADMIN_PASSWORD = "admin";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/practice";
  const setAuth = useAuthStore((s) => s.setAuth);
  const setHydrated = useAuthStore((s) => s.setHydrated);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loginWith(creds: { email: string; password: string }) {
    setError(null);
    setBusy(true);
    try {
      const resp = await fetch(`${BACKEND}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(creds),
      });
      if (!resp.ok) {
        setError(resp.status === 429 ? "Too many attempts. Try later." : "Invalid credentials.");
        return;
      }
      const data = await resp.json();
      setAuth(data.user, data.access_token, data.refresh_token);
      setHydrated(true);
      router.push(next);
    } finally {
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    void loginWith({ email, password });
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="mb-4 text-2xl font-bold">Log in</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          type="email"
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded border p-2"
          required
        />
        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded border p-2"
          required
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-primary p-2 text-primary-foreground disabled:opacity-50"
        >
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <button
        type="button"
        disabled={busy}
        onClick={() => void loginWith({ email: DEV_ADMIN_EMAIL, password: DEV_ADMIN_PASSWORD })}
        className="mt-3 w-full rounded border border-dashed border-gray-400 p-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        title={`Logs in as ${DEV_ADMIN_EMAIL} / ${DEV_ADMIN_PASSWORD}`}
      >
        Dev login (admin / admin)
      </button>
      <p className="mt-4 text-sm">
        No account?{" "}
        <a href="/register" className="text-primary underline">
          Register
        </a>
      </p>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
