"use client";

import { Runner } from "@/features/practice/runner";

export default function RunnerPage({ params }: { params: { id: string } }) {
  return <Runner sessionId={params.id} />;
}
