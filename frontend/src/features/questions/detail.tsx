"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useQuestionDetail,
  useReviewQuestion,
  useDeleteQuestion,
  useRevisions,
  useFeedbackList,
  useCreateFeedback,
} from "@/lib/api/questions";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { RequirePermission } from "@/components/require-permission";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { fmtDate } from "@/features/analytics/format";
import {
  STATUS_LABELS, statusVariant, availableActions,
  FEEDBACK_TYPE_LABELS, FEEDBACK_STATUS_LABELS,
} from "./labels";
import type { ReviewAction, FeedbackType } from "@/lib/api/types";

const FEEDBACK_TYPES: FeedbackType[] = [
  "unclear_explanation", "suspected_wrong_answer", "ambiguous_stem", "copyright_issue", "other",
];

export function QuestionDetailView({ questionId }: { questionId: string }) {
  const router = useRouter();
  const detail = useQuestionDetail(questionId);
  const review = useReviewQuestion(questionId);
  const del = useDeleteQuestion();
  const revisions = useRevisions(questionId);
  const feedback = useFeedbackList(questionId);
  const createFeedback = useCreateFeedback(questionId);

  const [fbType, setFbType] = useState<FeedbackType>("unclear_explanation");
  const [fbComment, setFbComment] = useState("");

  if (detail.isLoading) return <Loading label="Loading question…" />;
  if (detail.isError || !detail.data) return <ErrorState message="Could not load this question." />;
  const q = detail.data;

  function act(action: ReviewAction) {
    review.mutate({ action }, {
      onSuccess: () => toast.success("Status updated."),
      onError: () => toast.error("Could not update the status."),
    });
  }

  function remove() {
    del.mutate(questionId, {
      onSuccess: () => {
        toast.success("Question deleted.");
        router.push("/questions");
      },
      onError: () => toast.error("Could not delete the question."),
    });
  }

  function submitFeedback() {
    if (!fbComment.trim()) {
      toast.error("Add a comment describing the issue.");
      return;
    }
    createFeedback.mutate(
      { feedback_type: fbType, comment: fbComment.trim() },
      {
        onSuccess: () => {
          toast.success("Feedback submitted.");
          setFbComment("");
        },
        onError: () => toast.error("Could not submit feedback."),
      }
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Question"
        crumbs={["Questions"]}
        description={`v${q.version} · ${q.language} · ${q.question_type.replace(/_/g, " ")}`}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={statusVariant(q.status)}>{STATUS_LABELS[q.status]}</Badge>
            <RequirePermission perm="question:write">
              <Button asChild variant="outline" size="sm"><Link href={`/questions/${q.id}/edit`}>Edit</Link></Button>
            </RequirePermission>
          </div>
        }
      />

      <Card>
        <CardHeader><CardTitle className="text-base leading-relaxed">{q.stem}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {q.options.map((o) => (
            <div
              key={o.id ?? o.order_index}
              className={cn("flex items-start gap-2 rounded-md border p-2 text-sm", o.is_correct && "border-success/50 bg-success/10")}
            >
              <span className="font-mono text-xs text-muted-foreground">{o.order_index}</span>
              <div className="flex-1">
                <div>{o.content}</div>
                {o.explanation && <div className="mt-1 text-xs text-muted-foreground">{o.explanation}</div>}
              </div>
              {o.is_correct && <Badge variant="success">Correct</Badge>}
            </div>
          ))}
          {q.explanation && (
            <div className="mt-3 rounded-md bg-muted/40 p-3 text-sm">
              <div className="font-medium">Rationale</div>
              <p className="mt-1 leading-relaxed">{q.explanation.correct_answer_rationale}</p>
              {q.explanation.key_point_summary && (
                <p className="mt-2 text-muted-foreground">{q.explanation.key_point_summary}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <RequirePermission perm="question:publish">
        <Card>
          <CardHeader><CardTitle>Review</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {availableActions(q.status).length === 0 && (
              <p className="text-sm text-muted-foreground">No review actions available in this state.</p>
            )}
            {availableActions(q.status).map((a) => (
              <Button key={a.action} size="sm" variant="outline" disabled={review.isPending} onClick={() => act(a.action as ReviewAction)}>
                {a.label}
              </Button>
            ))}
          </CardContent>
        </Card>
      </RequirePermission>

      <Card>
        <CardHeader><CardTitle>Revision history</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {revisions.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {revisions.data && revisions.data.length === 0 && <p className="text-sm text-muted-foreground">No revisions yet.</p>}
          {revisions.data?.map((r) => (
            <div key={r.revision_number} className="flex items-center justify-between border-b py-1 text-sm last:border-0">
              <span>#{r.revision_number} {r.change_summary ? `· ${r.change_summary}` : ""}</span>
              <span className="text-muted-foreground">{fmtDate(r.edited_at)}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Correction feedback</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {feedback.data?.map((f) => (
              <div key={f.id} className="rounded-md border p-2 text-sm">
                <div className="flex items-center justify-between">
                  <Badge variant="outline">{FEEDBACK_TYPE_LABELS[f.feedback_type]}</Badge>
                  <span className="text-xs text-muted-foreground">{FEEDBACK_STATUS_LABELS[f.status]} · {fmtDate(f.created_at)}</span>
                </div>
                {f.comment && <p className="mt-1 text-muted-foreground">{f.comment}</p>}
              </div>
            ))}
            {feedback.data && feedback.data.length === 0 && <p className="text-sm text-muted-foreground">No feedback reported.</p>}
          </div>
          <div className="space-y-2 rounded-md border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Select value={fbType} onValueChange={(v) => setFbType(v as FeedbackType)}>
                <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                <SelectContent>{FEEDBACK_TYPES.map((t) => <SelectItem key={t} value={t}>{FEEDBACK_TYPE_LABELS[t]}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Textarea rows={2} value={fbComment} onChange={(e) => setFbComment(e.target.value)} placeholder="Describe the issue…" />
            <Button size="sm" onClick={submitFeedback} disabled={createFeedback.isPending}>Report feedback</Button>
          </div>
        </CardContent>
      </Card>

      <RequirePermission perm="question:write">
        <div className="flex justify-end">
          <Button variant="ghost" className="text-destructive" onClick={remove} disabled={del.isPending}>
            Delete question
          </Button>
        </div>
      </RequirePermission>
    </div>
  );
}
