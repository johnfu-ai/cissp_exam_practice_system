"use client";

import { useExamSession } from "@/lib/api/exam";
import { FixedExamRunner } from "./fixed-runner";
import { CatExamRunner } from "./cat-runner";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";

export function ExamRunner({ sessionId }: { sessionId: string }) {
  const session = useExamSession(sessionId);

  if (session.isLoading) return <Loading label="Loading exam…" />;
  if (session.isError || !session.data) {
    return <ErrorState message="Could not load this exam session." />;
  }
  const s = session.data;

  // A finished/expired session has no live delivery — send the user to the report.
  if (s.status !== "in_progress") {
    if (typeof window !== "undefined") {
      window.location.replace(`/exam/sessions/${sessionId}/report`);
    }
    return <Loading label="Loading report…" />;
  }

  if (s.session_kind === "cat") {
    return <CatExamRunner sessionId={sessionId} session={s} />;
  }
  return <FixedExamRunner sessionId={sessionId} session={s} />;
}
