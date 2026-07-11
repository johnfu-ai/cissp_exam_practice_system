"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useSession,
  useQuestion,
  useSubmitAnswer,
  usePauseSession,
  useResumeSession,
  useFinishSession,
  useUpdateQuestionState,
} from "@/lib/api/practice";
import {
  initialRunnerState,
  toggleSelection,
  canSubmit,
  markSubmitted,
  type RunnerState,
} from "./runner-machine";
import { OptionList } from "./option-list";
import { useSubmitShortcut } from "@/features/shared/use-submit-shortcut";
import { untrackSession } from "./session-tracker";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import { BilingualText } from "@/components/bilingual-text";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Bookmark, Flag, CheckCircle2, PauseCircle, PlayCircle, XCircle } from "lucide-react";
import type { ErrorType, LanguageMode, Localized } from "@/lib/api/types";

const ERROR_TYPES: ErrorType[] = [
  "concept_unclear",
  "misread_stem",
  "memory_lapse",
  "option_confusion",
  "time_pressure",
];
const LANGUAGE_MODES: LanguageMode[] = ["en", "zh", "bilingual"];

/** True when a Localized slot carries any translatable content. */
function hasContent(loc: Localized | null | undefined): boolean {
  return !!loc && (loc.en != null || loc.zh != null);
}

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Runner({ sessionId }: { sessionId: string }) {
  const t = useT();
  const router = useRouter();
  const [position, setPosition] = useState(0);
  const [runner, setRunner] = useState<RunnerState>(initialRunnerState(null));
  const [startedAt, setStartedAt] = useState<string>("");

  const session = useSession(sessionId);
  const question = useQuestion(sessionId, position);
  const submitAnswer = useSubmitAnswer(sessionId);
  const pause = usePauseSession(sessionId);
  const resume = useResumeSession(sessionId);
  const finish = useFinishSession(sessionId);
  const updateState = useUpdateQuestionState();

  const delivery = question.data;
  const paused = !!session.data?.paused_at;

  const [mode, setMode] = useState<LanguageMode>("en");
  useEffect(() => {
    if (delivery?.language_mode) setMode(delivery.language_mode);
  }, [delivery?.language_mode]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!delivery) return;
    setRunner(initialRunnerState(delivery.previous_answer));
    setStartedAt(new Date().toISOString());
  }, [delivery?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  function submit() {
    if (!delivery) return;
    submitAnswer.mutate(
      { position, selected: runner.selected, started_at: startedAt },
      {
        onSuccess: (result) => setRunner((s) => markSubmitted(s, result)),
        onError: (e) => {
          if (e instanceof ApiError && e.status === 409) {
            toast.error(t("practiceRunner.toastAlreadyAnswered"));
          } else {
            toast.error(t("practiceRunner.toastCouldNotSubmit"));
          }
        },
      }
    );
  }

  function next() {
    if (!delivery) return;
    if (position + 1 >= delivery.total) {
      finish.mutate(undefined, {
        onSuccess: () => {
          untrackSession(sessionId);
          router.push(`/practice/sessions/${sessionId}/done`);
        },
        onError: () => toast.error(t("practiceRunner.toastCouldNotFinish")),
      });
    } else {
      setPosition((p) => p + 1);
    }
  }

  function setQuestionState(body: Parameters<typeof updateState.mutate>[0]["body"]) {
    if (!delivery) return;
    updateState.mutate(
      { questionId: delivery.question_id, body },
      {
        onSuccess: () => toast.success(t("practiceRunner.toastSaved")),
        onError: () => toast.error(t("practiceRunner.toastCouldNotSave")),
      }
    );
  }

  // #34 / NFR-UX-04: Enter submits the current answer; once submitted, Enter
  // advances to the next question (or finishes). Placed before the early-return
  // guards so the hook order is stable across renders.
  useSubmitShortcut({
    onSubmit: submit,
    onNext: next,
    canSubmit:
      !!delivery &&
      runner.phase !== "submitted" &&
      canSubmit(runner) &&
      !paused &&
      !submitAnswer.isPending,
    canNext: runner.phase === "submitted" && !finish.isPending,
  });

  if (session.isError) {
    const stale = session.error instanceof ApiError && session.error.status === 409;
    return (
      <ErrorState
        title={stale ? t("practiceRunner.sessionUnavailable") : t("practiceRunner.couldNotLoadSession")}
        message={stale ? t("practiceRunner.sessionStaleMsg") : t("practiceRunner.retryMsg")}
        onRetry={() => router.push("/practice")}
      />
    );
  }
  if (session.isLoading || question.isLoading || !delivery) {
    return <Loading label={t("practiceRunner.loadingQuestion")} />;
  }
  if (question.isError) {
    return (
      <ErrorState
        message={t("practiceRunner.couldNotLoadQuestion")}
        onRetry={() => question.refetch()}
      />
    );
  }

  const submitted = runner.phase === "submitted";
  const result = runner.result;
  const progressPct =
    delivery.total > 0 ? ((delivery.position + 1) / delivery.total) * 100 : 0;

  return (
    <div className="mx-auto flex max-w-3xl flex-col">
      {/* Top: progress + controls */}
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            {t("practiceRunner.questionLabel")}{" "}
            <span className="font-medium text-foreground tabular-nums">{delivery.position + 1}</span>{" "}
            {t("practiceRunner.ofTotal")}{" "}
            <span className="tabular-nums">{delivery.total}</span>
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
            {paused ? (
              <Button variant="outline" size="sm" onClick={() => resume.mutate()}>
                <PlayCircle className="h-4 w-4" /> {t("practiceRunner.resume")}
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => pause.mutate()}>
                <PauseCircle className="h-4 w-4" /> {t("practiceRunner.pause")}
              </Button>
            )}
          </div>
        </div>
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={delivery.position + 1}
          aria-valuemin={1}
          aria-valuemax={delivery.total}
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
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{labelize(delivery.question_type)}</Badge>
          </div>
          <CardTitle className="mt-2 text-lg font-medium leading-relaxed">
            <BilingualText mode={mode} en={delivery.stem.en} zh={delivery.stem.zh} />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {paused ? (
            <p className="text-sm text-muted-foreground">{t("practiceRunner.sessionPaused")}</p>
          ) : (
            <OptionList
              questionType={delivery.question_type}
              options={delivery.options}
              selected={runner.selected}
              disabled={submitted || paused}
              onToggle={(i) => setRunner((s) => toggleSelection(s, i, delivery.question_type))}
              result={result}
              mode={mode}
            />
          )}

          {submitted && !result && delivery.previous_answer && (
            <p className="text-sm text-muted-foreground">
              {t("practiceRunner.alreadyAnsweredPrefix")}
              {delivery.previous_answer.is_correct
                ? t("practiceRunner.correctly")
                : t("practiceRunner.incorrectly")}
            </p>
          )}

          {submitted && result && (
            <div
              className={cn(
                "space-y-3 rounded-lg border p-4",
                result.is_correct
                  ? "border-success/30 bg-success/10"
                  : "border-destructive/30 bg-destructive/10"
              )}
            >
              <div className="flex items-center gap-2">
                {result.is_correct ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <XCircle className="h-5 w-5 text-destructive" />
                )}
                <span
                  className={cn(
                    "font-semibold",
                    result.is_correct ? "text-success" : "text-destructive"
                  )}
                >
                  {result.is_correct ? t("practiceRunner.correct") : t("practiceRunner.incorrect")}
                </span>
              </div>
              {hasContent(result.correct_rationale) && (
                <BilingualText
                  mode={mode}
                  en={result.correct_rationale.en}
                  zh={result.correct_rationale.zh}
                  className="text-sm leading-relaxed"
                />
              )}
              {hasContent(result.key_point_summary) && (
                <BilingualText
                  mode={mode}
                  en={result.key_point_summary.en}
                  zh={result.key_point_summary.zh}
                  className="text-sm text-muted-foreground"
                />
              )}
              {result.per_option.length > 0 && (
                <div className="space-y-2 border-t border-border pt-3">
                  {result.per_option.map((p) => (
                    <div key={p.order_index} className="text-sm">
                      <span
                        className={cn(
                          "font-medium",
                          p.is_correct ? "text-success" : "text-destructive"
                        )}
                      >
                        {t("practiceRunner.optionN", { n: p.order_index + 1 })}
                      </span>
                      {hasContent(p.explanation) && (
                        <BilingualText
                          mode={mode}
                          en={p.explanation.en}
                          zh={p.explanation.zh}
                          className="ml-2 inline-block text-muted-foreground"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sticky footer: per-question actions + primary navigation */}
      <div className="sticky bottom-0 z-10 mt-6 border-t bg-background/95 px-1 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {submitted && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuestionState({ is_bookmarked: true })}
                >
                  <Bookmark className="h-4 w-4" /> {t("practiceRunner.bookmark")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuestionState({ is_flagged_review: true })}
                >
                  <Flag className="h-4 w-4" /> {t("practiceRunner.flagReview")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuestionState({ is_mastered: true })}
                >
                  <CheckCircle2 className="h-4 w-4" /> {t("practiceRunner.markMastered")}
                </Button>
                <NoteDialog onSave={(note) => setQuestionState({ note })} t={t} />
                <Select onValueChange={(v) => setQuestionState({ error_type: v as ErrorType })}>
                  <SelectTrigger className="h-9 w-[200px]">
                    <SelectValue placeholder={t("practiceRunner.tagErrorType")} />
                  </SelectTrigger>
                  <SelectContent>
                    {ERROR_TYPES.map((et) => (
                      <SelectItem key={et} value={et}>
                        {labelize(et)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </>
            )}
          </div>
          <div className="flex justify-end gap-2">
            {!submitted ? (
              <Button
                size="pill"
                onClick={submit}
                disabled={!canSubmit(runner) || paused || submitAnswer.isPending}
              >
                {submitAnswer.isPending ? t("practiceRunner.submitting") : t("practiceRunner.submit")}
              </Button>
            ) : (
              <Button size="pill" onClick={next} disabled={finish.isPending}>
                {position + 1 >= delivery.total
                  ? finish.isPending
                    ? t("practiceRunner.finishing")
                    : t("practiceRunner.finish")
                  : t("practiceRunner.next")}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

type TFn = (key: string, vars?: Record<string, string | number>) => string;

function NoteDialog({ onSave, t }: { onSave: (note: string) => void; t: TFn }) {
  const [note, setNote] = useState("");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          {t("practiceRunner.addNote")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("practiceRunner.note")}</DialogTitle>
        </DialogHeader>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("practiceRunner.notePlaceholder")} />
        <DialogFooter>
          <DialogClose asChild>
            <Button onClick={() => onSave(note)}>{t("practiceRunner.saveNote")}</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
