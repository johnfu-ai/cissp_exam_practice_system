"use client";

import { use } from "react";
import { Runner } from "@/features/practice/runner";

export default function RunnerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <Runner sessionId={id} />;
}
