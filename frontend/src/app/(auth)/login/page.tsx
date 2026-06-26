"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, Lock, ShieldCheck } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/field";

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
    <div>
      <div className="mb-8 text-center">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary">
          <ShieldCheck className="h-6 w-6 text-primary-foreground" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">CISSP Exam Prep</h1>
        <p className="mt-1 text-sm text-muted-foreground">Master cybersecurity certification</p>
      </div>

      <Card className="rounded-2xl p-6 sm:p-8">
        <h2 className="mb-6 text-lg font-semibold">Log in</h2>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" htmlFor="signin-email" icon={Mail}>
            <Input
              id="signin-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          <Field label="Password" htmlFor="signin-password" icon={Lock}>
            <Input
              id="signin-password"
              type="password"
              autoComplete="current-password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" size="pill" className="w-full" disabled={busy}>
            {busy ? "Logging in…" : "Log in"}
          </Button>
        </form>
        <Button
          type="button"
          variant="outline"
          size="pill"
          className="mt-3 w-full border-dashed"
          disabled={busy}
          onClick={() => void loginWith({ email: DEV_ADMIN_EMAIL, password: DEV_ADMIN_PASSWORD })}
          title={`Logs in as ${DEV_ADMIN_EMAIL} / ${DEV_ADMIN_PASSWORD}`}
        >
          Dev login (admin / admin)
        </Button>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          No account?{" "}
          <a href="/register" className="font-medium text-primary hover:underline">
            Register
          </a>
        </p>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
