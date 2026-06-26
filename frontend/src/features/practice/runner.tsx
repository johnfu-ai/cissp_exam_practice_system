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
import { untrackSession } from "./session-tracker";
import { ApiError } from "@/lib/api";
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
const LANGUAGE_LABELS: Record<LanguageMode, string> = {
  en: "English",
  zh: "中文",
  bilingual: "Both",
};

/** True when a Localized slot carries any translatable content. */
function hasContent(loc: Localized | null | undefined): boolean {
  return !!loc && (loc.en != null || loc.zh != null);
}

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Runner({ sessionId }: { sessionId: string }) {
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

  // Local language mode for the in-runner toggle. Defaults to the session's
  // delivered `language_mode` and re-initialises whenever that changes (e.g. a
  // new session). Toggling only mutates this local state — it never refetches
  // and never touches selections or the timer (those are index/time based).
  const [mode, setMode] = useState<LanguageMode>("en");
  useEffect(() => {
    if (delivery?.language_mode) setMode(delivery.language_mode);
  }, [delivery?.language_mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset the per-question machine whenever a new question is delivered.
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
            toast.error("This question has already been answered.");
          } else {
            toast.error("Could not submit your answer.");
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
        onError: () => toast.error("Could not finish the session."),
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
        onSuccess: () => toast.success("Saved."),
        onError: () => toast.error("Could not save."),
      }
    );
  }

  if (session.isError) {
    const stale = session.error instanceof ApiError && session.error.status === 409;
    return (
      <ErrorState
        title={stale ? "Session unavailable" : "Could not load session"}
        message={stale ? "This session is finished or no longer available." : "Please go back and try again."}
        onRetry={() => router.push("/practice")}
      />
    );
  }
  if (session.isLoading || question.isLoading || !delivery) {
    return <Loading label="Loading question…" />;
  }
  if (question.isError) {
    return (
      <ErrorState
        message="Could not load this question."
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
            Question{" "}
            <span className="font-medium text-foreground tabular-nums">{delivery.position + 1}</span>{" "}
            of <span className="tabular-nums">{delivery.total}</span>
          </div>
          <div className="flex items-center gap-2">
            <Select value={mode} onValueChange={(v) => setMode(v as LanguageMode)}>
              <SelectTrigger className="h-9 w-[130px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_MODES.map((m) => (
                  <SelectItem key={m} value={m}>
                    {LANGUAGE_LABELS[m]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {paused ? (
              <Button variant="outline" size="sm" onClick={() => resume.mutate()}>
                <PlayCircle className="h-4 w-4" /> Resume
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => pause.mutate()}>
                <PauseCircle className="h-4 w-4" /> Pause
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
            <p className="text-sm text-muted-foreground">Session paused. Resume to continue.</p>
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
              You already answered this question
              {delivery.previous_answer.is_correct ? " correctly." : " incorrectly."}
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
                  {result.is_correct ? "Correct" : "Incorrect"}
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
                        Option {p.order_index + 1}
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
                  <Bookmark className="h-4 w-4" /> Bookmark
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuestionState({ is_flagged_review: true })}
                >
                  <Flag className="h-4 w-4" /> Flag for review
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuestionState({ is_mastered: true })}
                >
                  <CheckCircle2 className="h-4 w-4" /> Mark mastered
                </Button>
                <NoteDialog onSave={(note) => setQuestionState({ note })} />
                <Select onValueChange={(v) => setQuestionState({ error_type: v as ErrorType })}>
                  <SelectTrigger className="h-9 w-[200px]">
                    <SelectValue placeholder="Tag error type" />
                  </SelectTrigger>
                  <SelectContent>
                    {ERROR_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {labelize(t)}
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
                {submitAnswer.isPending ? "Submitting…" : "Submit"}
              </Button>
            ) : (
              <Button size="pill" onClick={next} disabled={finish.isPending}>
                {position + 1 >= delivery.total
                  ? finish.isPending
                    ? "Finishing…"
                    : "Finish"
                  : "Next"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function NoteDialog({ onSave }: { onSave: (note: string) => void }) {
  const [note, setNote] = useState("");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Add note
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Note</DialogTitle>
        </DialogHeader>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your note…" />
        <DialogFooter>
          <DialogClose asChild>
            <Button onClick={() => onSave(note)}>Save note</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
