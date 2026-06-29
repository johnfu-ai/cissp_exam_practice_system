// Pure label + badge helpers for the question bank — no React.
import type { TFn } from "@/lib/i18n/types";
import { enumLabel } from "@/features/shared/enum-label";
import type { QuestionStatus, FeedbackType, FeedbackStatus } from "@/lib/api/types";

export function statusLabel(t: TFn, status: QuestionStatus): string {
  return enumLabel(t, "qStatus", status);
}

export function feedbackTypeLabel(t: TFn, type: FeedbackType): string {
  return enumLabel(t, "feedbackType", type);
}

export function feedbackStatusLabel(t: TFn, status: FeedbackStatus): string {
  return enumLabel(t, "feedbackStatus", status);
}

type BadgeVariant = "default" | "secondary" | "success" | "destructive" | "outline";

export function statusVariant(status: QuestionStatus): BadgeVariant {
  switch (status) {
    case "published":
      return "success";
    case "pending_review":
      return "secondary";
    case "needs_revision":
      return "destructive";
    case "archived":
      return "outline";
    default:
      return "default";
  }
}

// Review actions available from a given status (mirrors the backend state
// machine). `labelKey` is a dotted dictionary path the caller resolves via
// `t(a.labelKey)`.
export function availableActions(status: QuestionStatus): { action: string; labelKey: string }[] {
  switch (status) {
    case "draft":
      return [{ action: "submit", labelKey: "qAction.submitReview" }];
    case "pending_review":
      return [
        { action: "approve", labelKey: "qAction.approvePublish" },
        { action: "request_changes", labelKey: "qAction.requestChanges" },
      ];
    case "published":
      return [{ action: "archive", labelKey: "qAction.archive" }];
    case "needs_revision":
      return [{ action: "submit", labelKey: "qAction.resubmitReview" }];
    case "archived":
      return [{ action: "restore", labelKey: "qAction.restoreDraft" }];
    default:
      return [];
  }
}
