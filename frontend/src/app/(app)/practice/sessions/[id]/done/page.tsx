"use client";

import { use } from "react";
import { Summary } from "@/features/practice/summary";

export default function DonePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <Summary sessionId={id} />;
}
