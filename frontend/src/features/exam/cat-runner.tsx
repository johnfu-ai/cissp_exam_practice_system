"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useExamNext, useSubmitExamAnswer, useFinishExam } from "@/lib/api/exam";
import { qk } from "@/lib/api/keys";
import { OptionList } from "@/features/practice/option-list";
import { untrackExam } from "./exam-tracker";
import { fmtCountdown, isTimeCritical } from "./format";
import { ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import type { ExamSession } from "@/lib/api/types";

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CatExamRunner({
  sessionId,
  session,
}: {
  sessionId: string;
  session: ExamSession;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");

  const next = useExamNext(sessionId);
  const submit = useSubmitExamAnswer(sessionId);
  const finish = useFinishExam(sessionId);

  const delivery = next.data;

  const deadlineRef = useRef<number | null>(null);
  const [remaining, setRemaining] = useState<number>(session.time_remaining_ms ?? 0);
  useEffect(() => {
    if (deadlineRef.current === null && session.time_remaining_ms != null) {
      deadlineRef.current = Date.now() + session.time_remaining_ms;
    }
  }, [session.time_remaining_ms]);
  // Keep the deadline fresh from each delivery's authoritative remaining time.
  useEffect(() => {
    if (delivery?.time_remaining_ms != null) {
      deadlineRef.current = Date.now() + delivery.time_remaining_ms;
    }
  }, [delivery?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const goReport = useCallback(() => {
    untrackExam(sessionId);
    router.push(`/exam/sessions/${sessionId}/report`);
  }, [router, sessionId]);

  const doFinish = useCallback(() => {
    finish.mutate(undefined, {
      onSuccess: goReport,
      onError: () => toast.error("Could not submit the exam."),
    });
  }, [finish, goReport]);

  const finishedRef = useRef(false);
  useEffect(() => {
    const t = setInterval(() => {
      if (deadlineRef.current === null) return;
      const ms = Math.max(0, deadlineRef.current - Date.now());
      setRemaining(ms);
      if (ms <= 0 && !finishedRef.current) {
        finishedRef.current = true;
        toast.message("Time is up — submitting your exam.");
        doFinish();
      }
    }, 1000);
    return () => clearInterval(t);
  }, [doFinish]);

  // Reset selection whenever a new adaptive item is delivered.
  useEffect(() => {
    if (!delivery) return;
    setSelected([]);
    setStartedAt(new Date().toISOString());
  }, [delivery?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(orderIndex: number) {
    if (!delivery) return;
    const isMulti = delivery.question_type === "multiple_choice";
    setSelected((cur) => {
      if (isMulti) {
        return cur.includes(orderIndex) ? cur.filter((x) => x !== orderIndex) : [...cur, orderIndex];
      }
      return [orderIndex];
    });
  }

  function submitAndAdvance() {
    if (!delivery || selected.length === 0) return;
    submit.mutate(
      { position: delivery.position, selected, started_at: startedAt },
      {
        onSuccess: (ack) => {
          if (ack.finished) {
            goReport();
            return;
          }
          // Forward-only: fetch the next adaptively-selected item.
          qc.invalidateQueries({ queryKey: qk.exam.next(sessionId) });
        },
        onError: (e) => {
          if (e instanceof ApiError && (e.status === 409 || e.status === 422)) {
            toast.error("The exam is no longer in progress.");
            goReport();
          } else {
            toast.error("Could not submit your answer.");
          }
        },
      }
    );
  }

  if (next.isError) {
    const stale = next.error instanceof ApiError && next.error.status === 409;
    return (
      <ErrorState
        title={stale ? "Exam ended" : "Could not load question"}
        message={stale ? "This adaptive exam is finished or timed out." : "Please try again."}
        onRetry={stale ? goReport : () => next.refetch()}
      />
    );
  }
  if (next.isLoading || !delivery) return <Loading label="Selecting your next question…" />;

  const critical = isTimeCritical(remaining);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Question {delivery.position + 1}
          {delivery.total > 0 ? ` (up to ${delivery.total})` : ""}
        </div>
        <div
          className={cn(
            "rounded-md px-3 py-1 font-mono text-sm tabular-nums",
            critical ? "bg-destructive text-destructive-foreground" : "bg-muted"
          )}
          aria-label="Time remaining"
        >
          {fmtCountdown(remaining)}
        </div>
      </div>

      <Alert>
        <AlertTitle>Adaptive — forward only</AlertTitle>
        <AlertDescription>
          Once you submit an answer you cannot return to it. This is a study tool and does not
          represent an official ISC2 score.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <Badge variant="secondary" className="w-fit">{labelize(delivery.question_type)}</Badge>
          <CardTitle className="mt-2 text-lg font-medium leading-relaxed">{delivery.stem}</CardTitle>
        </CardHeader>
        <CardContent>
          <OptionList
            questionType={delivery.question_type}
            options={delivery.options}
            selected={selected}
            disabled={submit.isPending}
            onToggle={toggle}
            result={null}
          />
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={submitAndAdvance} disabled={selected.length === 0 || submit.isPending}>
          {submit.isPending ? "Submitting…" : "Submit & continue"}
        </Button>
      </div>
    </div>
  );
}
