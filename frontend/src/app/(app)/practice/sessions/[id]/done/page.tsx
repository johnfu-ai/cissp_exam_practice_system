"use client";

import { Summary } from "@/features/practice/summary";

export default function DonePage({ params }: { params: { id: string } }) {
  return <Summary sessionId={params.id} />;
}
