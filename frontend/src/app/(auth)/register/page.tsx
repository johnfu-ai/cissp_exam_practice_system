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

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const resp = await fetch(`${BACKEND}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName || null }),
    });
    if (!resp.ok) {
      const t = await resp.text();
      setError(resp.status === 409 ? "Email already registered." : t);
      return;
    }
    const data = await resp.json();
    setAuth(data.user, data.access_token, data.refresh_token);
    router.push("/");
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
        <h2 className="mb-6 text-lg font-semibold">Register</h2>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" htmlFor="signup-email" icon={Mail}>
            <Input
              id="signup-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          <Field label="Display name" htmlFor="signup-name" icon={User}>
            <Input
              id="signup-name"
              type="text"
              autoComplete="name"
              placeholder="Optional"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </Field>
          <Field label="Password" htmlFor="signup-password" icon={Lock}>
            <Input
              id="signup-password"
              type="password"
              autoComplete="new-password"
              placeholder="Min 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" size="pill" className="w-full">
            Register
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-primary hover:underline">
            Log in
          </a>
        </p>
      </Card>
    </div>
  );
}
