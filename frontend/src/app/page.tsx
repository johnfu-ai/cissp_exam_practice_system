"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/auth-store";
import { apiJson } from "@/lib/api";

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

export default function Home() {
  const { user, accessToken, hydrate, clear } = useAuthStore();
  const [health, setHealth] = useState<string>("...");
  const [datasets, setDatasets] = useState<string>("");

  useEffect(() => {
    hydrate();
    fetch(`${BACKEND}/health`)
      .then((r) => r.json())
      .then((j) => setHealth(JSON.stringify(j)))
      .catch(() => setHealth("error"));
  }, [hydrate]);

  async function loadDatasets() {
    try {
      const ds = await apiJson<any[]>("/api/etl/datasets");
      setDatasets(ds.map((d) => d.slug).join(", "));
    } catch (e: any) {
      setDatasets(`error: ${e.message}`);
    }
  }

  async function logout() {
    const rt = useAuthStore.getState().refreshToken;
    if (rt) {
      await fetch(`${BACKEND}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
    }
    clear();
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold mb-2">CISSP Exam Practice</h1>
      <p className="text-gray-600 mb-6">Backend health: {health}</p>
      {accessToken && user ? (
        <div className="space-y-4">
          <p>
            Signed in as <strong>{user.email}</strong> (roles: {user.roles.join(", ")})
          </p>
          <button onClick={logout} className="border px-4 py-2 rounded">
            Log out
          </button>
          <div>
            <button
              onClick={loadDatasets}
              className="bg-blue-600 text-white px-4 py-2 rounded"
            >
              List ETL datasets
            </button>
            {datasets && <p className="mt-2 text-sm">datasets: {datasets}</p>}
          </div>
        </div>
      ) : (
        <div className="space-x-4">
          <a href="/login" className="bg-blue-600 text-white px-4 py-2 rounded inline-block">
            Log in
          </a>
          <a href="/register" className="border px-4 py-2 rounded inline-block">
            Register
          </a>
        </div>
      )}
    </main>
  );
}
