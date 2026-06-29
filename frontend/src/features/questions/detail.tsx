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
import { useT } from "@/lib/i18n/provider";
import { enumLabel } from "@/features/shared/enum-label";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { fmtDate } from "@/features/analytics/format";
import {
  statusLabel, statusVariant, availableActions,
  feedbackTypeLabel, feedbackStatusLabel,
} from "./labels";
import type { ReviewAction, FeedbackType, LanguageCode } from "@/lib/api/types";

const FEEDBACK_TYPES: FeedbackType[] = [
  "unclear_explanation", "suspected_wrong_answer", "ambiguous_stem", "copyright_issue", "other",
];

// Presentational only: elevates the positive publish action as the primary
// button in the review state-machine control row. Does not alter the state
// machine itself (labels + available actions live in ./labels, tested).
const REVIEW_ACTION_VARIANT: Record<string, "default" | "outline"> = {
  approve: "default",
};

/** Compact badge label for a question's available languages. */
function langBadge(languages: LanguageCode[]): string {
  const hasEn = languages.includes("en");
  const hasZh = languages.includes("zh");
  if (hasEn && hasZh) return "EN+中";
  if (hasZh) return "中";
  if (hasEn) return "EN";
  return "—";
}

export function QuestionDetailView({ questionId }: { questionId: string }) {
  const t = useT();
  const router = useRouter();
  const detail = useQuestionDetail(questionId);
  const review = useReviewQuestion(questionId);
  const del = useDeleteQuestion();
  const revisions = useRevisions(questionId);
  const feedback = useFeedbackList(questionId);
  const createFeedback = useCreateFeedback(questionId);

  const [fbType, setFbType] = useState<FeedbackType>("unclear_explanation");
  const [fbComment, setFbComment] = useState("");

  if (detail.isLoading) return <Loading label={t("questionDetail.loadingQuestion")} />;
  if (detail.isError || !detail.data) return <ErrorState message={t("questionDetail.loadFailed")} />;
  const q = detail.data;

  // Canonical correctness keyed by order_index (shared across translations).
  const correctByOrder = new Map<number, boolean>();
  q.options.forEach((o) => {
    if (o.order_index != null) correctByOrder.set(o.order_index, o.is_correct);
  });

  function act(action: ReviewAction) {
    review.mutate({ action }, {
      onSuccess: () => toast.success(t("questionDetail.toastStatusUpdated")),
      onError: () => toast.error(t("questionDetail.toastCouldNotUpdateStatus")),
    });
  }

  function remove() {
    del.mutate(questionId, {
      onSuccess: () => {
        toast.success(t("questionDetail.toastDeleted"));
        router.push("/questions");
      },
      onError: () => toast.error(t("questionDetail.toastCouldNotDelete")),
    });
  }

  function submitFeedback() {
    if (!fbComment.trim()) {
      toast.error(t("questionDetail.toastNeedComment"));
      return;
    }
    createFeedback.mutate(
      { feedback_type: fbType, comment: fbComment.trim() },
      {
        onSuccess: () => {
          toast.success(t("questionDetail.toastFeedbackSubmitted"));
          setFbComment("");
        },
        onError: () => toast.error(t("questionDetail.toastCouldNotSubmitFeedback")),
      }
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow={t("questions.eyebrow")}
        title={t("questionDetail.title")}
        crumbs={[t("nav.questions")]}
        description={t("questionDetail.desc", { version: q.version, lang: langBadge(q.available_languages), type: enumLabel(t, "qType", q.question_type) })}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={statusVariant(q.status)}>{statusLabel(t, q.status)}</Badge>
            <RequirePermission perm="question:write">
              <Button asChild variant="outline" size="sm"><Link href={`/questions/${q.id}/edit`}>{t("questionDetail.edit")}</Link></Button>
            </RequirePermission>
          </div>
        }
      />

      {q.translations.map((tr) => (
        <Card key={tr.language}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base leading-relaxed">{tr.stem}</CardTitle>
            <Badge variant="outline">{t(`lang.${tr.language}`)}</Badge>
          </CardHeader>
          <CardContent className="space-y-2">
            {tr.options.map((o) => {
              const isCorrect = correctByOrder.get(o.order_index) ?? false;
              return (
                <div
                  key={o.order_index}
                  className={cn("flex items-start gap-2 rounded-md border p-2 text-sm", isCorrect && "border-success/50 bg-success/10")}
                >
                  <span className="font-mono text-xs text-muted-foreground">{o.order_index}</span>
                  <div className="flex-1">
                    <div>{o.content}</div>
                    {o.explanation && <div className="mt-1 text-xs text-muted-foreground">{o.explanation}</div>}
                  </div>
                  {isCorrect && <Badge variant="success">{t("questionDetail.correct")}</Badge>}
                </div>
              );
            })}
            <div className="mt-3 rounded-md bg-muted/40 p-3 text-sm">
              <div className="font-medium">{t("questionDetail.rationale")}</div>
              <p className="mt-1 leading-relaxed">{tr.correct_answer_rationale}</p>
              {tr.key_point_summary && (
                <p className="mt-2 text-muted-foreground">{tr.key_point_summary}</p>
              )}
            </div>
          </CardContent>
        </Card>
      ))}

      <RequirePermission perm="question:publish">
        <Card>
          <CardHeader><CardTitle>{t("questionDetail.reviewTitle")}</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {availableActions(q.status).length === 0 && (
              <p className="text-sm text-muted-foreground">{t("questionDetail.noReviewActions")}</p>
            )}
            {availableActions(q.status).map((a) => (
              <Button key={a.action} size="sm" variant={REVIEW_ACTION_VARIANT[a.action] ?? "outline"} disabled={review.isPending} onClick={() => act(a.action as ReviewAction)}>
                {t(a.labelKey)}
              </Button>
            ))}
          </CardContent>
        </Card>
      </RequirePermission>

      <Card>
        <CardHeader><CardTitle>{t("questionDetail.revisionHistory")}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {revisions.isLoading && <p className="text-sm text-muted-foreground">{t("questionDetail.loading")}</p>}
          {revisions.data && revisions.data.length === 0 && <p className="text-sm text-muted-foreground">{t("questionDetail.noRevisions")}</p>}
          {revisions.data?.map((r) => (
            <div key={r.revision_number} className="flex items-center justify-between border-b py-1 text-sm last:border-0">
              <span>#{r.revision_number} {r.change_summary ? `· ${r.change_summary}` : ""}</span>
              <span className="text-muted-foreground">{fmtDate(r.edited_at)}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("questionDetail.correctionFeedback")}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {feedback.data?.map((f) => (
              <div key={f.id} className="rounded-md border p-2 text-sm">
                <div className="flex items-center justify-between">
                  <Badge variant="outline">{feedbackTypeLabel(t, f.feedback_type)}</Badge>
                  <span className="text-xs text-muted-foreground">{feedbackStatusLabel(t, f.status)} · {fmtDate(f.created_at)}</span>
                </div>
                {f.comment && <p className="mt-1 text-muted-foreground">{f.comment}</p>}
              </div>
            ))}
            {feedback.data && feedback.data.length === 0 && <p className="text-sm text-muted-foreground">{t("questionDetail.noFeedback")}</p>}
          </div>
          <div className="space-y-2 rounded-md border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Select value={fbType} onValueChange={(v) => setFbType(v as FeedbackType)}>
                <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                <SelectContent>{FEEDBACK_TYPES.map((ft) => <SelectItem key={ft} value={ft}>{feedbackTypeLabel(t, ft)}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Textarea rows={2} value={fbComment} onChange={(e) => setFbComment(e.target.value)} placeholder={t("questionDetail.describeIssue")} />
            <Button size="sm" onClick={submitFeedback} disabled={createFeedback.isPending}>{t("questionDetail.reportFeedback")}</Button>
          </div>
        </CardContent>
      </Card>

      <RequirePermission perm="question:write">
        <div className="flex justify-end">
          <Button variant="ghost" className="text-destructive" onClick={remove} disabled={del.isPending}>
            {t("questionDetail.deleteQuestion")}
          </Button>
        </div>
      </RequirePermission>
    </div>
  );
}
