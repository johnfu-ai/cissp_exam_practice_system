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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
import { Bookmark, Flag, CheckCircle2, PauseCircle, PlayCircle } from "lucide-react";
import type { ErrorType } from "@/lib/api/types";

const ERROR_TYPES: ErrorType[] = [
  "concept_unclear",
  "misread_stem",
  "memory_lapse",
  "option_confusion",
  "time_pressure",
];

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

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Question {delivery.position + 1} of {delivery.total}
        </div>
        <div className="flex items-center gap-2">
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

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{labelize(delivery.question_type)}</Badge>
          </div>
          <CardTitle className="mt-2 text-lg font-medium leading-relaxed">{delivery.stem}</CardTitle>
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
            />
          )}

          {submitted && !result && delivery.previous_answer && (
            <p className="text-sm text-muted-foreground">
              You already answered this question
              {delivery.previous_answer.is_correct ? " correctly." : " incorrectly."}
            </p>
          )}

          {submitted && result && (
            <div className="space-y-3 rounded-md border bg-muted/30 p-4">
              <div className={result.is_correct ? "font-medium text-success" : "font-medium text-destructive"}>
                {result.is_correct ? "Correct" : "Incorrect"}
              </div>
              {result.correct_rationale && (
                <p className="text-sm leading-relaxed">{result.correct_rationale}</p>
              )}
              {result.key_point_summary && (
                <p className="text-sm text-muted-foreground">{result.key_point_summary}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {submitted && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setQuestionState({ is_bookmarked: true })}>
              <Bookmark className="h-4 w-4" /> Bookmark
            </Button>
            <Button variant="outline" size="sm" onClick={() => setQuestionState({ is_flagged_review: true })}>
              <Flag className="h-4 w-4" /> Flag for review
            </Button>
            <Button variant="outline" size="sm" onClick={() => setQuestionState({ is_mastered: true })}>
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
          </div>
          <Separator />
        </>
      )}

      <div className="flex justify-end gap-2">
        {!submitted ? (
          <Button onClick={submit} disabled={!canSubmit(runner) || paused || submitAnswer.isPending}>
            {submitAnswer.isPending ? "Submitting…" : "Submit"}
          </Button>
        ) : (
          <Button onClick={next} disabled={finish.isPending}>
            {position + 1 >= delivery.total ? (finish.isPending ? "Finishing…" : "Finish") : "Next"}
          </Button>
        )}
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
