"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

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
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-2xl font-bold mb-4">Register</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input type="email" placeholder="email" value={email}
               onChange={(e) => setEmail(e.target.value)} className="border p-2 rounded" required />
        <input type="text" placeholder="display name (optional)" value={displayName}
               onChange={(e) => setDisplayName(e.target.value)} className="border p-2 rounded" />
        <input type="password" placeholder="password (min 8)" value={password}
               onChange={(e) => setPassword(e.target.value)} className="border p-2 rounded" required />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="bg-blue-600 text-white p-2 rounded">Register</button>
      </form>
    </main>
  );
}
