"use client";

// Paper-bank-style paper player (PRD v1.4 FR-PAPER-05/07): timer, answer sheet
// with 4-state legend, per-question navigation with auto-save, bilingual
// toggle, flag/bookmark, essay textarea + self-assessment, submit.
//
// Invariants (tested): the language-mode toggle is pure client state — it
// never submits, never advances; exam answers auto-save on navigation.
//
// PRD v1.5 (FR-PAPER-11..13): the sheet never collapses while a question
// loads (stable total), the palette scrolls inside a bounded region, mount
// restores sheet/timer/progress from the server resume bundle, and paper
// sessions can switch mode mid-flight.
//
// PRD v1.7 (FR-PAPER-12): timing is ACTIVE time for both modes — the player
// heartbeats on mount / every 20s / pagehide (keepalive) to the unified
// papers endpoint, and the exam countdown derives from the server's
// duration_budget_seconds − elapsed (away time never counts).
//
// PRD v1.6 (FR-PAPER-05 restyle): big blue timer, a segmented practice⇄exam
// mode switch, current-question outline on the palette, a green auto-save
// pill, a paper-title header, type tag + 纠错/标记/收藏 icon actions, radio
// option indicators, and a bottom prev/next bar — matching the reference
// reference layout.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bookmark, Flag, MessageSquareWarning } from "lucide-react";
import { apiJson } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { BilingualText, localizedText } from "@/components/bilingual-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loading } from "@/components/loading";
import { enumLabel } from "@/features/shared/enum-label";
import { usePreferences } from "@/lib/api/preferences";
import { usePaperDetail } from "@/lib/api/papers";
import {
  useExamQuestion,
  useExamSelfAssess,
  useFinishExam,
  useFinishPractice,
  usePracticeQuestion,
  usePracticeSelfAssess,
  useSetQuestionState,
  useSubmitExamAnswer,
  useSubmitPracticeAnswer,
} from "@/lib/api/sessions";
import type {
  AnswerResult,
  FeedbackType,
  LanguageMode,
  PaperSessionState,
  QuestionDelivery,
} from "@/lib/api/types";
import {
  cellStatus,
  emptySheet,
  formatClock,
  remainingMs,
  sheetCounts,
  type AnswerSheetState,
} from "./answer-sheet";

const nowIso = () => new Date().toISOString();
const HEARTBEAT_INTERVAL_MS = 20_000;

const FEEDBACK_TYPES: FeedbackType[] = [
  "unclear_explanation",
  "suspected_wrong_answer",
  "ambiguous_stem",
  "copyright_issue",
  "other",
];

export function PaperPlayer({
  sessionId,
  kind,
  paperId,
}: {
  sessionId: string;
  kind: "practice" | "exam";
  paperId?: string;
}) {
  const t = useT();
  const router = useRouter();
  const { data: prefs } = usePreferences();
  const paperDetail = usePaperDetail(paperId ?? null);
  const [mode, setMode] = useState<LanguageMode>("en");
  useEffect(() => {
    if (prefs?.language_mode) setMode(prefs.language_mode);
  }, [prefs?.language_mode]);

  const [position, setPosition] = useState(0);
  const [sheet, setSheet] = useState<AnswerSheetState>(emptySheet);
  const [selection, setSelection] = useState<number[]>([]);
  const [essayText, setEssayText] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [startedEpoch, setStartedEpoch] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);
  const [practiceSummary, setPracticeSummary] = useState<{
    answered: number;
    correct: number;
    accuracy: number;
  } | null>(null);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [bookmarked, setBookmarked] = useState(false);
  const [fbOpen, setFbOpen] = useState(false);
  const [fbType, setFbType] = useState<FeedbackType>("unclear_explanation");
  const [fbComment, setFbComment] = useState("");
  const [fbSent, setFbSent] = useState(false);
  const [fbSending, setFbSending] = useState(false);
  const questionStart = useRef(0);

  // FR-PAPER-12: fetch the resume bundle once on mount — restores the answer
  // sheet, timer base (practice) / deadline (exam), and jumps to the first
  // unanswered question. No `alive` cancellation: reactStrictMode double-runs
  // effects in dev, and the run-once guard would combine with the first run's
  // cleanup into a fetch whose result is always discarded.
  const resumeFetched = useRef(false);
  useEffect(() => {
    if (resumeFetched.current) return;
    resumeFetched.current = true;
    apiJson<PaperSessionState>(`/api/papers/sessions/${sessionId}/state`)
      .then((st) => {
        if (st.status !== "in_progress") return;
        const answered: Record<number, boolean> = {};
        const wrong: Record<number, boolean> = {};
        for (const p of st.answered_positions) answered[p] = true;
        for (const p of st.wrong_positions) wrong[p] = true;
        setSheet({ answered, wrong, flagged: {} });
        if (st.kind === "practice" && st.elapsed_seconds != null) {
          const base = Date.now() - st.elapsed_seconds * 1000;
          setStartedEpoch(base);
          // seed in the same batch so the first resumed render already shows
          // the carried-over base (the ticker effect re-syncs afterwards)
          setElapsed(Date.now() - base);
        }
        if (st.kind === "exam") {
          // v1.7 active-time budget: countdown = budget − accumulated active
          // time (away time never consumed it). Legacy exams fall back to the
          // server deadline.
          if (st.duration_budget_seconds != null && st.elapsed_seconds != null) {
            setDeadline(
              Date.now() +
                Math.max(
                  0,
                  (st.duration_budget_seconds - st.elapsed_seconds) * 1000,
                ),
            );
          } else if (st.deadline_at) {
            setDeadline(new Date(st.deadline_at).getTime());
          }
        }
        if (st.total > 0) {
          const answeredSet = new Set(st.answered_positions);
          let first = 0;
          while (first < st.total && answeredSet.has(first)) first += 1;
          setPosition(first >= st.total ? 0 : first);
        }
      })
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    // set immediately so a resumed timer shows the carried-over base at once
    setElapsed(Date.now() - startedEpoch);
    const timer = window.setInterval(() => setElapsed(Date.now() - startedEpoch), 1000);
    return () => window.clearInterval(timer);
  }, [startedEpoch]);

  // FR-PAPER-12 (v1.7): unified active-time heartbeat for BOTH modes — the
  // exam countdown is budget − accumulated active time. Fires immediately on
  // mount (truncating any away-window grace), then every 20s, and a
  // keepalive fetch on pagehide reports the final elapsed so the clock
  // stops at exit. Time away from the player is never counted.
  const startedRef = useRef(startedEpoch);
  useEffect(() => {
    startedRef.current = startedEpoch;
  }, [startedEpoch]);
  const reportElapsed = useCallback(
    (keepalive = false) => {
      apiJson(`/api/papers/sessions/${sessionId}/heartbeat`, {
        method: "POST",
        body: JSON.stringify({
          elapsed_seconds: Math.max(
            0,
            Math.floor((Date.now() - startedRef.current) / 1000),
          ),
        }),
        ...(keepalive ? { keepalive: true } : {}),
      }).catch(() => {});
    },
    [sessionId],
  );
  useEffect(() => {
    if (finished) return;
    reportElapsed();
    const id = window.setInterval(() => reportElapsed(), HEARTBEAT_INTERVAL_MS);
    const onPageHide = () => reportElapsed(true);
    const onVisibility = () => {
      if (document.visibilityState === "hidden") reportElapsed(true);
    };
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [finished, reportElapsed]);

  const practiceQ = usePracticeQuestion(sessionId, position, kind === "practice" && !finished);
  const examQ = useExamQuestion(sessionId, position, kind === "exam" && !finished);
  const q: QuestionDelivery | undefined = kind === "practice" ? practiceQ.data : examQ.data;
  const isLoading = kind === "practice" ? practiceQ.isLoading : examQ.isLoading;

  const submitPractice = useSubmitPracticeAnswer(sessionId);
  const submitExam = useSubmitExamAnswer(sessionId);
  const selfAssessPractice = usePracticeSelfAssess(sessionId);
  const selfAssessExam = useExamSelfAssess(sessionId);
  const finishPractice = useFinishPractice(sessionId);
  const finishExam = useFinishExam(sessionId);
  const setState = useSetQuestionState();

  // FR-PAPER-13: the sheet total is stable for the whole session — it must
  // not collapse (and shove the submit button around) while a question load
  // is in flight.
  const [stableTotal, setStableTotal] = useState(0);
  useEffect(() => {
    if (q?.total) setStableTotal(q.total);
  }, [q?.total]);
  const total = stableTotal;

  const counts = useMemo(() => sheetCounts(sheet, total), [sheet, total]);
  const isEssay = q?.question_type === "essay";

  // hydrate current-question inputs from any previous answer (resume)
  const hydratedFor = useRef<string>("");
  useEffect(() => {
    if (!q) return;
    const key = `${q.position}`;
    if (hydratedFor.current === key) return;
    hydratedFor.current = key;
    setSelection(q.previous_answer?.selected ?? []);
    setEssayText(q.previous_answer?.text ?? "");
    setBookmarked(false);
    if (q.previous_answer && (q.previous_answer.selected?.length || q.previous_answer.text)) {
      setSheet((s) => ({ ...s, answered: { ...s.answered, [q.position]: true } }));
    }
    if (q.previous_answer?.is_correct === false) {
      setSheet((s) => ({ ...s, wrong: { ...s.wrong, [q.position]: true } }));
    }
    setResult(null);
    questionStart.current = Date.now();
  }, [q]);

  const commitExamAnswer = useCallback(
    async (pos: number) => {
      if (kind !== "exam") return;
      await submitExam.mutateAsync({
        position: pos,
        selected: isEssay ? [] : selection,
        answer_text: isEssay ? essayText : undefined,
        started_at: nowIso(),
      });
      setSheet((s) => ({
        ...s,
        answered: {
          ...s.answered,
          [pos]: !isEssay ? selection.length > 0 : essayText.trim().length > 0,
        },
      }));
    },
    [kind, submitExam, isEssay, selection, essayText],
  );

  async function submitPracticeAnswer() {
    if (!q) return;
    const res = await submitPractice.mutateAsync({
      position: q.position,
      selected: isEssay ? [] : selection,
      answer_text: isEssay ? essayText : undefined,
      started_at: nowIso(),
    });
    setResult(res);
    setSheet((s) => ({
      ...s,
      answered: { ...s.answered, [q.position]: true },
      wrong:
        res.is_correct === false
          ? { ...s.wrong, [q.position]: true }
          : s.wrong,
    }));
  }

  async function assessSelf(correct: boolean) {
    if (!q) return;
    if (kind === "practice") {
      await selfAssessPractice.mutateAsync({ position: q.position, correct });
      setResult((r) => (r ? { ...r, is_correct: correct } : r));
      if (!correct) {
        setSheet((s) => ({ ...s, wrong: { ...s.wrong, [q.position]: true } }));
      }
    } else {
      await selfAssessExam.mutateAsync({ position: q.position, correct });
    }
  }

  async function goto(newPosition: number) {
    if (newPosition < 0 || (total && newPosition >= total)) return;
    if (kind === "exam" && !finished) {
      try {
        await commitExamAnswer(position);
      } catch {
        /* keep navigating; the next save retries */
      }
    }
    setPosition(newPosition);
  }

  async function submitPaper() {
    if (kind === "exam") {
      try {
        if (!finished) await commitExamAnswer(position);
      } catch {
        /* finish judges whatever was saved */
      }
      await finishExam.mutateAsync();
      window.location.href = `/paper-play/${sessionId}/report`;
      return;
    }
    const summary = await finishPractice.mutateAsync();
    setFinished(true);
    setPracticeSummary({
      answered: summary.answered_count,
      correct: summary.correct_count,
      accuracy: summary.accuracy,
    });
  }

  // exam time-up auto submit
  useEffect(() => {
    if (kind !== "exam" || deadline === null || finished) return;
    if (remainingMs(deadline, startedEpoch + elapsed) <= 0) {
      submitPaper();
    }
  }, [elapsed, kind, deadline, finished]); // eslint-disable-line react-hooks/exhaustive-deps

  // FR-PAPER-11: convert this paper session to the other mode; the server
  // copies answers and time, we just route to the new session.
  async function switchMode() {
    if (!paperId || switching) return;
    const target = kind === "practice" ? "exam" : "practice";
    setSwitching(true);
    setSwitchError(null);
    try {
      const result = await apiJson<{
        session_id: string;
        kind: "practice" | "exam";
      }>(`/api/papers/sessions/${sessionId}/switch-mode`, {
        method: "POST",
        body: JSON.stringify({ mode: target }),
      });
      router.replace(
        `/paper-play/${result.session_id}?kind=${result.kind}&paper=${paperId}`,
      );
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      try {
        const parsed = JSON.parse(raw) as { detail?: string };
        setSwitchError(parsed?.detail ?? raw);
      } catch {
        setSwitchError(raw);
      }
      setSwitching(false);
    }
  }

  function toggleFlag() {
    if (!q) return;
    const next = !sheet.flagged[q.position];
    setSheet((s) => ({ ...s, flagged: { ...s.flagged, [q.position]: next } }));
    setState.mutate({ question_id: q.question_id, is_flagged_review: next });
  }

  function toggleBookmark() {
    if (!q) return;
    const next = !bookmarked;
    setBookmarked(next);
    setState.mutate({ question_id: q.question_id, is_bookmarked: next });
  }

  // FR-PAPER-05 (v1.6): 纠错 — send correction feedback for the current
  // question straight from the player.
  async function sendFeedback() {
    if (!q || fbSending) return;
    setFbSending(true);
    try {
      await apiJson(`/api/questions/${q.question_id}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          feedback_type: fbType,
          comment: fbComment.trim() ? fbComment.trim() : null,
        }),
      });
      setFbSent(true);
    } catch {
      /* keep the dialog open so the learner can retry */
    } finally {
      setFbSending(false);
    }
  }

  const stemCell = q ? { en: q.stem.en, zh: q.stem.zh } : null;

  return (
    <div className="mx-auto flex w-full max-w-6xl gap-6 p-6">
      {/* Left rail: big timer + mode switch + answer sheet + submit */}
      <Card className="sticky top-6 h-fit w-64 shrink-0 space-y-4 p-5">
        <div>
          <div className="text-xs text-muted-foreground">
            {kind === "exam" ? t("paperPlay.remaining") : t("paperPlay.elapsed")}
          </div>
          <div
            className="font-mono text-3xl font-semibold tabular-nums text-primary"
            aria-label="timer"
            data-testid="paper-timer"
          >
            {kind === "exam"
              ? deadline === null
                ? "--:--"
                : formatClock(remainingMs(deadline, startedEpoch + elapsed))
              : formatClock(elapsed)}
          </div>
        </div>

        {paperId && !finished ? (
          <div className="space-y-1">
            <div
              role="group"
              aria-label={t("paperPlay.modeSwitch")}
              className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1"
            >
              <button
                type="button"
                disabled={kind === "practice" || switching}
                aria-pressed={kind === "practice"}
                onClick={() => {
                  if (kind !== "practice") void switchMode();
                }}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  kind === "practice"
                    ? "bg-background text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t("paperPlay.practiceMode")}
              </button>
              <button
                type="button"
                disabled={kind === "exam" || switching}
                aria-pressed={kind === "exam"}
                onClick={() => {
                  if (kind !== "exam") void switchMode();
                }}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  kind === "exam"
                    ? "bg-background text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t("paperPlay.examMode")}
              </button>
            </div>
            {switchError && (
              <p className="text-xs text-destructive" role="alert">
                {switchError}
              </p>
            )}
          </div>
        ) : (
          <Badge variant={kind === "exam" ? "default" : "secondary"}>
            {kind === "exam" ? t("paperPlay.examMode") : t("paperPlay.practiceMode")}
          </Badge>
        )}

        {total > 0 && (
          <div>
            <div
              role="region"
              aria-label={t("paperPlay.palette")}
              className="max-h-[50vh] overflow-y-auto pr-1"
            >
              <div className="mb-2 grid grid-cols-5 gap-1.5">
                {Array.from({ length: total }, (_, i) => {
                  const status = cellStatus(sheet, i);
                  const cls =
                    status === "answered"
                      ? "bg-primary text-primary-foreground"
                      : status === "wrong"
                        ? "bg-destructive text-white"
                        : status === "flagged"
                          ? "border-2 border-amber-400 text-foreground"
                          : "border text-muted-foreground";
                  return (
                    <button
                      key={i}
                      type="button"
                      aria-label={`question ${i + 1} ${status}`}
                      onClick={() => goto(i)}
                      className={`h-8 rounded text-xs font-medium transition-colors ${cls} ${
                        i === position
                          ? "border-2 border-primary bg-background font-semibold text-primary"
                          : ""
                      }`}
                    >
                      {i + 1}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-primary" />
                {t("paperPlay.answered")} ({counts.answered})
              </div>
              <div className="flex items-center gap-1.5 text-destructive">
                <span className="h-2 w-2 rounded-full bg-destructive" />
                {t("paperPlay.wrong")} ({counts.wrong})
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
                {t("paperPlay.unanswered")} ({counts.unanswered})
              </div>
              <div className="flex items-center gap-1.5 text-amber-500">
                <span className="h-2 w-2 rounded-amber-400 bg-amber-400" />
                {t("paperPlay.flagged")} ({counts.flagged})
              </div>
            </div>
          </div>
        )}

        <div className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          {t("paperPlay.autoSave")}
        </div>
        <Button
          variant="destructive"
          className="w-full"
          disabled={finished || finishPractice.isPending || finishExam.isPending}
          onClick={submitPaper}
        >
          {finishPractice.isPending || finishExam.isPending
            ? t("paperPlay.finishing")
            : kind === "exam"
              ? t("paperPlay.submit")
              : t("paperPlay.finishPractice")}
        </Button>
      </Card>

      {/* Main column */}
      <div className="min-w-0 flex-1 space-y-4">
        {/* paper-bank-style paper header (FR-PAPER-05, v1.6) */}
        {paperId && paperDetail.data && !practiceSummary && (
          <Card className="space-y-1 p-4">
            <h1 className="text-base font-semibold leading-snug">
              {paperDetail.data.name}
            </h1>
            <p className="flex flex-wrap gap-x-4 text-xs text-muted-foreground">
              {paperDetail.data.duration_minutes != null && (
                <span>
                  {t("papersPage.duration", {
                    minutes: paperDetail.data.duration_minutes,
                  })}
                </span>
              )}
              <span>{t("papersPage.score", { score: paperDetail.data.total_score })}</span>
              <span>
                {t("papersPage.questionCount", {
                  count: paperDetail.data.question_count,
                })}
              </span>
            </p>
          </Card>
        )}

        {practiceSummary && (
          <Card className="space-y-2 p-6">
            <h2 className="font-semibold">{t("paperPlay.summaryTitle")}</h2>
            <p className="text-sm text-muted-foreground">
              {t("paperPlay.answered")}: {practiceSummary.answered} ·{" "}
              {t("paperPlay.correct")}: {practiceSummary.correct} ·{" "}
              {t("paperPlay.accuracy")}:{" "}
              {(practiceSummary.accuracy * 100).toFixed(0)}%
            </p>
            <div className="flex gap-2 pt-2">
              <Button asChild size="sm" variant="outline">
                <Link href="/wrong-book">{t("paperPlay.viewWrongBook")}</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/papers">{t("paperPlay.backToPapers")}</Link>
              </Button>
            </div>
          </Card>
        )}

        {isLoading || !q ? (
          <div className="p-8">
            <Loading label={t("common.loading")} />
          </div>
        ) : (
          <Card className="space-y-4 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                  {enumLabel(t, "qType", q.question_type as never)}
                </span>
                <span className="text-sm font-medium">
                  {t("paperPlay.question", { n: q.position + 1, total: q.total })}
                </span>
              </div>
              <div className="flex items-center gap-1">
                {(q.available_languages.length > 1 || mode !== "bilingual") && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setMode(
                        mode === "en" ? "zh" : mode === "zh" ? "bilingual" : "en",
                      )
                    }
                    aria-label="language mode"
                  >
                    {mode === "en" ? "EN" : mode === "zh" ? "中文" : "EN/中文"}
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={t("paperPlay.reportError")}
                  onClick={() => {
                    setFbSent(false);
                    setFbOpen(true);
                  }}
                >
                  <MessageSquareWarning className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={t("paperPlay.flag")}
                  onClick={toggleFlag}
                  className={sheet.flagged[q.position] ? "text-amber-500" : ""}
                >
                  <Flag className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={
                    bookmarked ? t("paperPlay.bookmarked") : t("paperPlay.bookmark")
                  }
                  onClick={toggleBookmark}
                  className={bookmarked ? "text-primary" : ""}
                >
                  <Bookmark className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {stemCell && (
              <BilingualText
                mode={mode}
                en={stemCell.en}
                zh={stemCell.zh}
                className="text-base leading-relaxed"
              />
            )}

            {isEssay ? (
              <textarea
                value={essayText}
                onChange={(e) => setEssayText(e.target.value)}
                placeholder={t("paperPlay.essayPlaceholder")}
                rows={6}
                disabled={kind === "practice" && result !== null}
                className="w-full rounded-md border bg-background p-3 text-sm"
                aria-label="essay answer"
              />
            ) : (
              <div className="space-y-2">
                {q.options.map((o) => {
                  const chosen = selection.includes(o.order_index);
                  const reveal = result
                    ? result.correct_indexes.includes(o.order_index)
                    : false;
                  const wrongPick =
                    result && chosen && !result.correct_indexes.includes(o.order_index);
                  const multi = q.question_type === "multiple_choice";
                  return (
                    <button
                      key={o.order_index}
                      type="button"
                      disabled={kind === "practice" && result !== null}
                      onClick={() =>
                        setSelection((sel) =>
                          q.question_type === "multiple_choice"
                            ? sel.includes(o.order_index)
                              ? sel.filter((x) => x !== o.order_index)
                              : [...sel, o.order_index].sort((a, b) => a - b)
                            : [o.order_index],
                        )
                      }
                      className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left text-sm transition-colors ${
                        reveal
                          ? "border-success bg-success/10"
                          : wrongPick
                            ? "border-destructive bg-destructive/10"
                            : chosen
                              ? "border-primary bg-primary/5"
                              : "hover:bg-accent"
                      }`}
                    >
                      <span
                        aria-hidden
                        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center border-2 ${
                          multi ? "rounded-[4px]" : "rounded-full"
                        } ${
                          chosen
                            ? "border-primary bg-primary"
                            : "border-muted-foreground/40"
                        }`}
                      >
                        {chosen && (
                          <span
                            className={`${multi ? "" : "rounded-full"} h-1.5 w-1.5 bg-primary-foreground`}
                          />
                        )}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="mr-2 font-semibold">
                          {String.fromCharCode(65 + o.order_index)}.
                        </span>
                        {localizedText(mode, { en: o.content.en, zh: o.content.zh })}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Practice feedback / essay self-assessment */}
            {kind === "practice" && result && (
              <div className="space-y-3 rounded-lg border bg-muted/40 p-4 text-sm">
                {result.is_correct === null ? (
                  <p className="font-medium">{t("paperPlay.pendingSelfAssess")}</p>
                ) : (
                  <p
                    className={`font-semibold ${
                      result.is_correct ? "text-success" : "text-destructive"
                    }`}
                  >
                    {result.is_correct
                      ? t("paperPlay.correct")
                      : t("paperPlay.incorrect")}
                  </p>
                )}
                {isEssay && result.reference_answer && (
                  <div>
                    <div className="mb-1 font-medium">
                      {t("paperPlay.referenceAnswer")}
                    </div>
                    <BilingualText
                      mode={mode}
                      en={result.reference_answer.en}
                      zh={result.reference_answer.zh}
                    />
                  </div>
                )}
                {result.correct_rationale &&
                  (result.correct_rationale.en || result.correct_rationale.zh) && (
                    <div>
                      <div className="mb-1 font-medium">{t("paperPlay.rationale")}</div>
                      <BilingualText
                        mode={mode}
                        en={result.correct_rationale.en}
                        zh={result.correct_rationale.zh}
                      />
                    </div>
                  )}
                {!isEssay && result.per_option.length > 0 && (
                  <div className="space-y-1">
                    {result.per_option
                      .filter(
                        (p) => p.explanation.en || p.explanation.zh,
                      )
                      .map((p) => (
                        <div key={p.order_index} className="text-muted-foreground">
                          <span className="font-medium">
                            {String.fromCharCode(65 + p.order_index)}.{" "}
                          </span>
                          {localizedText(mode, { en: p.explanation.en, zh: p.explanation.zh })}
                        </div>
                      ))}
                  </div>
                )}
                {isEssay && result.is_correct === null && (
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => assessSelf(true)}>
                      {t("paperPlay.iWasRight")}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => assessSelf(false)}>
                      {t("paperPlay.iWasWrong")}
                    </Button>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={position === 0}
                onClick={() => goto(position - 1)}
              >
                {t("paperPlay.prev")}
              </Button>
              {kind === "practice" && !result ? (
                <Button
                  size="sm"
                  disabled={isEssay ? !essayText.trim() : selection.length === 0}
                  onClick={submitPracticeAnswer}
                >
                  {t("common.submit")}
                </Button>
              ) : (
                <span aria-hidden />
              )}
              <Button
                size="sm"
                disabled={total > 0 && position >= total - 1}
                onClick={() => goto(position + 1)}
              >
                {t("paperPlay.next")}
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* 纠错 feedback dialog (FR-PAPER-05, v1.6) */}
      <Dialog open={fbOpen} onOpenChange={setFbOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("paperPlay.feedbackTitle")}</DialogTitle>
          </DialogHeader>
          {fbSent ? (
            <div className="space-y-3">
              <p className="text-sm text-success">{t("paperPlay.feedbackSent")}</p>
              <DialogFooter>
                <Button size="sm" variant="outline" onClick={() => setFbOpen(false)}>
                  {t("common.cancel")}
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-3">
              <Select value={fbType} onValueChange={(v) => setFbType(v as FeedbackType)}>
                <SelectTrigger className="w-full" aria-label={t("paperPlay.feedbackType")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FEEDBACK_TYPES.map((v) => (
                    <SelectItem key={v} value={v}>
                      {enumLabel(t, "feedbackType", v)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <textarea
                aria-label={t("paperPlay.feedbackComment")}
                value={fbComment}
                onChange={(e) => setFbComment(e.target.value)}
                rows={3}
                placeholder={t("paperPlay.feedbackComment")}
                className="w-full rounded-md border bg-background p-3 text-sm"
              />
              <DialogFooter>
                <Button size="sm" variant="outline" onClick={() => setFbOpen(false)}>
                  {t("common.cancel")}
                </Button>
                <Button size="sm" disabled={fbSending} onClick={sendFeedback}>
                  {t("common.submit")}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
