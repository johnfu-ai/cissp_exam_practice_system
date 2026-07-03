"use client";

import { useState } from "react";
import Link from "next/link";
import { Mail, Lock, KeyRound } from "lucide-react";
import { BACKEND } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/field";
import { useT } from "@/lib/i18n/provider";
import { toast } from "@/components/ui/sonner";

const inputCls = "border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0";

export function ForgotPasswordView() {
  const t = useT();
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function requestReset(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const resp = await fetch(`${BACKEND}/api/auth/reset-password/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (resp.status === 429) {
        setError(t("auth.tooManyAttempts"));
        return;
      }
      // Always 200 otherwise (no email enumeration). In development the token
      // is returned so the flow is testable end-to-end without email infra.
      const data = await resp.json().catch(() => ({}));
      if (data.token) setToken(data.token);
      setStep(2);
    } finally {
      setBusy(false);
    }
  }

  async function confirmReset(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const resp = await fetch(`${BACKEND}/api/auth/reset-password/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      if (!resp.ok) {
        setError(t("auth.resetFailed"));
        return;
      }
      setDone(true);
      toast.success(t("auth.passwordReset"));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <Card className="rounded-2xl p-6 text-center sm:p-8">
        <p className="text-sm text-muted-foreground">{t("auth.passwordReset")}</p>
        <Button asChild size="pill" className="mt-4 w-full">
          <Link href="/login">{t("auth.backToLogin")}</Link>
        </Button>
      </Card>
    );
  }

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary">
          <KeyRound className="h-6 w-6 text-primary-foreground" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("auth.forgotPasswordTitle")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("auth.forgotPasswordDesc")}</p>
      </div>

      <Card className="rounded-2xl p-6 sm:p-8">
        {step === 1 ? (
          <form onSubmit={requestReset} className="space-y-4">
            <Field label={t("auth.email")} htmlFor="fp-email" icon={Mail}>
              <Input
                id="fp-email"
                type="email"
                autoComplete="email"
                placeholder={t("auth.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputCls}
                required
              />
            </Field>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" size="pill" className="w-full" disabled={busy}>
              {busy ? t("auth.sending") : t("auth.sendResetLink")}
            </Button>
          </form>
        ) : (
          <form onSubmit={confirmReset} className="space-y-4">
            <p className="text-sm text-muted-foreground">{t("auth.resetSent")}</p>
            <Field label={t("auth.resetToken")} htmlFor="fp-token" icon={KeyRound}>
              <Input
                id="fp-token"
                value={token}
                placeholder={t("auth.resetTokenPlaceholder")}
                onChange={(e) => setToken(e.target.value)}
                className={inputCls}
                required
              />
            </Field>
            <Field label={t("auth.newPassword")} htmlFor="fp-new" icon={Lock}>
              <Input
                id="fp-new"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={inputCls}
                minLength={8}
                required
              />
            </Field>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" size="pill" className="w-full" disabled={busy}>
              {busy ? t("auth.resetting") : t("auth.confirmReset")}
            </Button>
          </form>
        )}
        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link href="/login" className="font-medium text-primary hover:underline">
            {t("auth.backToLogin")}
          </Link>
        </p>
      </Card>
    </div>
  );
}
