"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Mail, Lock, ShieldCheck, User } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/field";
import { useT } from "@/lib/i18n/provider";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const t = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const resp = await fetch(`${BACKEND}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, display_name: displayName || null }),
        credentials: "include",
      });
      if (!resp.ok) {
        // #30: don't surface the raw backend body (leaks impl detail / ugly JSON);
        // show a friendly message, with a specific one for the duplicate-email case.
        setError(resp.status === 409 ? t("auth.emailExists") : t("auth.registerFailed"));
        return;
      }
      const data = await resp.json();
      setAuth(data.user, data.access_token);
      router.push("/");
    } catch {
      // #30: network failure / server unreachable -> fetch rejects.
      setError(t("auth.networkError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary">
          <ShieldCheck className="h-6 w-6 text-primary-foreground" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.brand")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("auth.tagline")}</p>
      </div>

      <Card className="rounded-2xl p-6 sm:p-8">
        <h2 className="mb-6 text-lg font-semibold">{t("auth.register")}</h2>
        <form onSubmit={submit} className="space-y-4">
          <Field label={t("auth.email")} htmlFor="signup-email" icon={Mail}>
            <Input
              id="signup-email"
              type="email"
              autoComplete="email"
              placeholder={t("auth.emailPlaceholder")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          <Field label={t("auth.displayName")} htmlFor="signup-name" icon={User}>
            <Input
              id="signup-name"
              type="text"
              autoComplete="name"
              placeholder={t("auth.optional")}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </Field>
          <Field label={t("auth.password")} htmlFor="signup-password" icon={Lock}>
            <Input
              id="signup-password"
              type="password"
              autoComplete="new-password"
              placeholder={t("auth.passwordHint")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" size="pill" className="w-full" disabled={busy}>
            {t("auth.register")}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {t("auth.haveAccount")}{" "}
          <a href="/login" className="font-medium text-primary hover:underline">
            {t("auth.login")}
          </a>
        </p>
      </Card>
    </div>
  );
}
