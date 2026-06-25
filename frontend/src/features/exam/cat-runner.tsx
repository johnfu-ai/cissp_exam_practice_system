"use client";

import type { ExamSession } from "@/lib/api/types";
import { EmptyState } from "@/components/empty-state";

// Placeholder — replaced by the full forward-only CAT runner in sub-project I5.
export function CatExamRunner({ session }: { sessionId: string; session: ExamSession }) {
  return (
    <EmptyState
      title="CAT delivery is being finalized"
      description={`Adaptive exam ${session.id} — runner coming in the next release.`}
    />
  );
}
