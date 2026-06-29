"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useExamQuestion,
  useSubmitExamAnswer,
  useFinishExam,
} from "@/lib/api/exam";
import { OptionList } from "@/features/practice/option-list";
import { untrackExam } from "./exam-tracker";
import { fmtCountdown, isTimeCritical } from "./format";
import { ApiError } from "@/lib/api";
import { BilingualText } from "@/components/bilingual-text";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import { enumLabel } from "@/features/shared/enum-label";
import type { ExamSession, LanguageMode } from "@/lib/api/types";

const LANGUAGE_MODES: LanguageMode[] = ["en", "zh", "bilingual"];

export function FixedExamRunner({
  sessionId,
  session,
}: {
  sessionId: string;
  session: ExamSession;
}) {
  const t = useT();
  const router = useRouter();
  const [position, setPosition] = useState(0);
  const [selections, setSelections] = useState<Record<number, number[]>>({});
  const [answered, setAnswered] = useState<Set<number>>(new Set());
  const [startedAt, setStartedAt] = useState<string>("");
  const total = session.total_questions;

  const question = useExamQuestion(sessionId, position);
  const submit = useSubmitExamAnswer(sessionId);
  const finish = useFinishExam(sessionId);

  const delivery = question.data;

  // Local language mode for the in-runner toggle. Defaults to the session's
  // delivered `language_mode` and re-initialises whenever that changes (e.g. a
  // new question with a different session mode). Toggling only mutates this
  // local state — it never refetches and never touches `selections[position]`
  // or the question palette (those are index based).
  const [mode, setMode] = useState<LanguageMode>(delivery?.language_mode ?? "en");
  useEffect(() => {
    if (delivery?.language_mode) setMode(delivery.language_mode);
  }, [delivery?.language_mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Absolute deadline derived once from the server's remaining time.
  const deadlineRef = useRef<number | null>(null);
  const [remaining, setRemaining] = useState<number>(session.time_remaining_ms ?? 0);
  useEffect(() => {
    if (deadlineRef.current === null && session.time_remaining_ms != null) {
      deadlineRef.current = Date.now() + session.time_remaining_ms;
    }
  }, [session.time_remaining_ms]);

  const goReport = useCallback(() => {
    untrackExam(sessionId);
    router.push(`/exam/sessions/${sessionId}/report`);
  }, [router, sessionId]);

  const doFinish = useCallback(() => {
    finish.mutate(undefined, {
      onSuccess: goReport,
      onError: () => toast.error(t("examRunner.toastCouldNotSubmitExam")),
    });
  }, [finish, goReport, t]);

  // Tick the countdown; auto-submit when it hits zero.
  const finishedRef = useRef(false);
  useEffect(() => {
    const interval = setInterval(() => {
      if (deadlineRef.current === null) return;
      const ms = Math.max(0, deadlineRef.current - Date.now());
      setRemaining(ms);
      if (ms <= 0 && !finishedRef.current) {
        finishedRef.current = true;
        toast.message(t("examRunner.toastTimeUp"));
        doFinish();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [doFinish, t]);

  // Seed selection from the server's stored answer the first time we see a question.
  useEffect(() => {
    if (!delivery) return;
    setStartedAt(new Date().toISOString());
    setSelections((prev) => {
      if (prev[delivery.position] !== undefined) return prev;
      const sel = delivery.previous_answer?.selected ?? [];
      return { ...prev, [delivery.position]: sel };
    });
    if (delivery.previous_answer) {
      setAnswered((prev) => new Set(prev).add(delivery.position));
    }
  }, [delivery?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const selected = selections[position] ?? [];

  function toggle(orderIndex: number) {
    if (!delivery) return;
    const isMulti = delivery.question_type === "multiple_choice";
    setSelections((prev) => {
      const cur = prev[position] ?? [];
      let next: number[];
      if (isMulti) {
        next = cur.includes(orderIndex) ? cur.filter((x) => x !== orderIndex) : [...cur, orderIndex];
      } else {
        next = [orderIndex];
      }
      return { ...prev, [position]: next };
    });
  }

  // Save the current selection (revisable upsert), then run `after`.
  function save(after?: () => void) {
    if (!delivery || selected.length === 0) {
      after?.();
      return;
    }
    submit.mutate(
      { position, selected, started_at: startedAt },
      {
        onSuccess: (ack) => {
          setAnswered((prev) => new Set(prev).add(position));
          if (deadlineRef.current !== null) {
            deadlineRef.current = Date.now() + ack.time_remaining_ms;
          }
          if (ack.finished) {
            goReport();
            return;
          }
          after?.();
        },
        onError: (e) => {
          if (e instanceof ApiError && e.status === 409) {
            toast.error(t("examRunner.toastExamNotInProgress"));
            goReport();
          } else {
            toast.error(t("examRunner.toastCouldNotSaveAnswer"));
          }
        },
      }
    );
  }

  function goTo(p: number) {
    if (p < 0 || p >= total) return;
    save(() => setPosition(p));
  }

  if (question.isError) {
    const stale = question.error instanceof ApiError && question.error.status === 409;
    return (
      <ErrorState
        title={stale ? t("examRunner.errExamEnded") : t("examRunner.errCouldNotLoadQuestion")}
        message={stale ? t("examRunner.errExamStaleFixed") : t("examRunner.errRetry")}
        onRetry={stale ? goReport : () => question.refetch()}
      />
    );
  }
  if (question.isLoading || !delivery) return <Loading label={t("examRunner.loadingQuestion")} />;

  const critical = isTimeCritical(remaining);
  const progressPct = total > 0 ? ((position + 1) / total) * 100 : 0;

  return (
    <div className="mx-auto flex max-w-3xl flex-col">
      {/* Top: progress + controls */}
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            {t("examRunner.questionLabel")}{" "}
            <span className="font-medium text-foreground tabular-nums">{position + 1}</span>{" "}
            {t("examRunner.ofTotal")}{" "}
            <span className="tabular-nums">{total}</span>
          </div>
          <div className="flex items-center gap-2">
            <Select value={mode} onValueChange={(v) => setMode(v as LanguageMode)}>
              <SelectTrigger className="h-9 w-[130px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_MODES.map((m) => (
                  <SelectItem key={m} value={m}>
                    {t(`lang.${m}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div
              className={cn(
                "rounded-full px-3 py-1 font-mono text-sm font-semibold tabular-nums",
                critical ? "bg-destructive text-destructive-foreground" : "bg-muted",
              )}
              aria-label={t("examRunner.timeRemainingAria")}
            >
              {fmtCountdown(remaining)}
            </div>
          </div>
        </div>
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={position + 1}
          aria-valuemin={1}
          aria-valuemax={total}
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Question card */}
      <Card className="mt-6">
        <CardHeader>
          <Badge variant="secondary" className="w-fit">{enumLabel(t, "qType", delivery.question_type)}</Badge>
          <CardTitle className="mt-2 text-lg font-medium leading-relaxed">
            <BilingualText mode={mode} en={delivery.stem.en} zh={delivery.stem.zh} />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <OptionList
            questionType={delivery.question_type}
            options={delivery.options}
            selected={selected}
            disabled={false}
            onToggle={toggle}
            result={null}
            mode={mode}
          />
        </CardContent>
      </Card>

      {/* Question palette */}
      <Card className="mt-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-normal text-muted-foreground">{t("examRunner.palette")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5">
            {Array.from({ length: total }, (_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => goTo(i)}
                className={cn(
                  "h-8 w-8 rounded-md text-xs font-medium transition-colors",
                  i === position
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : answered.has(i)
                      ? "bg-success/20 text-foreground hover:bg-success/30"
                      : "bg-muted hover:bg-accent",
                )}
                aria-label={`${t("examRunner.goToQuestionAria", { n: i + 1 })}${answered.has(i) ? ` ${t("examRunner.answered")}` : ""}`}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Sticky footer: navigation + finish */}
      <div className="sticky bottom-0 z-10 mt-6 border-t bg-background/95 px-1 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="flex items-center justify-between gap-3">
          <Button variant="outline" onClick={() => goTo(position - 1)} disabled={position === 0 || submit.isPending}>
            {t("examRunner.previous")}
          </Button>
          <div className="flex gap-2">
            {position + 1 < total ? (
              <Button size="pill" onClick={() => goTo(position + 1)} disabled={submit.isPending}>
                {submit.isPending ? t("examRunner.saving") : t("examRunner.saveNext")}
              </Button>
            ) : (
              <Button onClick={() => save()} disabled={submit.isPending} variant="outline">
                {t("examRunner.save")}
              </Button>
            )}
            <FinishDialog
              answered={answered.size}
              total={total}
              onConfirm={() => save(doFinish)}
              pending={finish.isPending}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function FinishDialog({
  answered,
  total,
  onConfirm,
  pending,
}: {
  answered: number;
  total: number;
  onConfirm: () => void;
  pending: boolean;
}) {
  const t = useT();
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>{t("examRunner.finishExam")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("examRunner.submitDialogTitle")}</DialogTitle>
          <DialogDescription>
            {t("examRunner.submitDialogDesc", { answered, total })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t("examRunner.keepWorking")}</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button onClick={onConfirm} disabled={pending}>
              {pending ? t("examRunner.submitting") : t("examRunner.submitExam")}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
