"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const resp = await fetch(`${BACKEND}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) {
      setError(resp.status === 429 ? "Too many attempts. Try later." : "Invalid credentials.");
      return;
    }
    const data = await resp.json();
    setAuth(data.user, data.access_token, data.refresh_token);
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-2xl font-bold mb-4">Log in</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input type="email" placeholder="email" value={email}
               onChange={(e) => setEmail(e.target.value)} className="border p-2 rounded" required />
        <input type="password" placeholder="password" value={password}
               onChange={(e) => setPassword(e.target.value)} className="border p-2 rounded" required />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="bg-blue-600 text-white p-2 rounded">Log in</button>
      </form>
      <p className="mt-4 text-sm">
        No account? <a href="/register" className="text-blue-600 underline">Register</a>
      </p>
    </main>
  );
}
