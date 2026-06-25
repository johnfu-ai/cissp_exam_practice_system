// Pure label + badge helpers for the question bank — no React.
import type { QuestionStatus, FeedbackType, FeedbackStatus } from "@/lib/api/types";

export const STATUS_LABELS: Record<QuestionStatus, string> = {
  draft: "Draft",
  pending_review: "Pending review",
  published: "Published",
  needs_revision: "Needs revision",
  archived: "Archived",
};

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

export const FEEDBACK_TYPE_LABELS: Record<FeedbackType, string> = {
  unclear_explanation: "Unclear explanation",
  suspected_wrong_answer: "Suspected wrong answer",
  ambiguous_stem: "Ambiguous stem",
  copyright_issue: "Copyright issue",
  other: "Other",
};

export const FEEDBACK_STATUS_LABELS: Record<FeedbackStatus, string> = {
  open: "Open",
  resolved: "Resolved",
  wont_fix: "Won't fix",
};

// Review actions available from a given status (mirrors the backend state machine).
export function availableActions(status: QuestionStatus): { action: string; label: string }[] {
  switch (status) {
    case "draft":
      return [{ action: "submit", label: "Submit for review" }];
    case "pending_review":
      return [
        { action: "approve", label: "Approve & publish" },
        { action: "request_changes", label: "Request changes" },
      ];
    case "published":
      return [{ action: "archive", label: "Archive" }];
    case "needs_revision":
      return [{ action: "submit", label: "Resubmit for review" }];
    case "archived":
      return [{ action: "restore", label: "Restore to draft" }];
    default:
      return [];
  }
}
