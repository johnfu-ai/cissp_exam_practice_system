"use client";

// paper-bank-style paper player (PRD v1.4 FR-PAPER-05/07): timer, answer sheet
// with 4-state legend, per-question navigation with auto-save, bilingual
// toggle, flag/bookmark, essay textarea + self-assessment, submit.
//
// Invariants (tested): the language-mode toggle is pure client state — it
// never submits, never advances; exam answers auto-save on navigation.
//
// PRD v1.5 (FR-PAPER-11..13): the sheet never collapses while a question
// loads (stable total), the palette scrolls inside a bounded region, mount
// restores sheet/timer/progress from the server resume bundle, practice time
// heartbeats to the server, and paper sessions can switch mode mid-flight.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiJson } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { BilingualText, localizedText } from "@/components/bilingual-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loading } from "@/components/loading";
import { enumLabel } from "@/features/shared/enum-label";
import { usePreferences } from "@/lib/api/preferences";
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
  const questionStart = useRef(0);

  // FR-PAPER-12: fetch the resume bundle once on mount — restores the answer
  // sheet, timer base (practice) / deadline (exam), and jumps to the first
  // unanswered question.
  const resumeFetched = useRef(false);
  useEffect(() => {
    if (resumeFetched.current) return;
    resumeFetched.current = true;
    let alive = true;
    apiJson<PaperSessionState>(`/api/papers/sessions/${sessionId}/state`)
      .then((st) => {
        if (!alive || st.status !== "in_progress") return;
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
        if (st.kind === "exam" && st.deadline_at) {
          setDeadline(new Date(st.deadline_at).getTime());
        }
        if (st.total > 0) {
          const answeredSet = new Set(st.answered_positions);
          let first = 0;
          while (first < st.total && answeredSet.has(first)) first += 1;
          setPosition(first >= st.total ? 0 : first);
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [sessionId]);

  useEffect(() => {
    // set immediately so a resumed timer shows the carried-over base at once
    setElapsed(Date.now() - startedEpoch);
    const timer = window.setInterval(() => setElapsed(Date.now() - startedEpoch), 1000);
    return () => window.clearInterval(timer);
  }, [startedEpoch]);

  // FR-PAPER-12: report accumulated practice time so exits don't lose it;
  // time away from the player is not counted (server grace window).
  const startedRef = useRef(startedEpoch);
  useEffect(() => {
    startedRef.current = startedEpoch;
  }, [startedEpoch]);
  useEffect(() => {
    if (kind !== "practice" || finished) return;
    const id = window.setInterval(() => {
      apiJson(`/api/practice/sessions/${sessionId}/heartbeat`, {
        method: "POST",
        body: JSON.stringify({
          elapsed_seconds: Math.max(
            0,
            Math.floor((Date.now() - startedRef.current) / 1000),
          ),
        }),
      }).catch(() => {});
    }, HEARTBEAT_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [kind, finished, sessionId]);

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

  const stemCell = q ? { en: q.stem.en, zh: q.stem.zh } : null;

  return (
    <div className="mx-auto flex w-full max-w-6xl gap-6 p-6">
      {/* Left rail: timer + answer sheet + submit (mock-paper layout) */}
      <Card className="sticky top-6 h-fit w-60 shrink-0 space-y-4 p-4">
        <div className="text-xs text-muted-foreground">
          {kind === "exam" ? t("paperPlay.remaining") : t("paperPlay.elapsed")}
        </div>
        <div className="font-mono text-2xl font-semibold tabular-nums" aria-label="timer">
          {kind === "exam"
            ? deadline === null
              ? "--:--"
              : formatClock(remainingMs(deadline, startedEpoch + elapsed))
            : formatClock(elapsed)}
        </div>
        <Badge variant={kind === "exam" ? "default" : "secondary"}>
          {kind === "exam" ? t("paperPlay.examMode") : t("paperPlay.practiceMode")}
        </Badge>
        {paperId && !finished && (
          <div className="space-y-1">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              disabled={switching}
              onClick={switchMode}
            >
              {kind === "practice"
                ? t("paperPlay.switchToExam")
                : t("paperPlay.switchToPractice")}
            </Button>
            {switchError && (
              <p className="text-xs text-destructive" role="alert">
                {switchError}
              </p>
            )}
          </div>
        )}
        {total > 0 && (
          <div>
            <div
              role="region"
              aria-label={t("paperPlay.palette")}
              className="max-h-[50vh] overflow-y-auto pr-1"
            >
              <div className="mb-2 grid grid-cols-6 gap-1.5">
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
                        i === position ? "ring-2 ring-ring" : ""
                      }`}
                    >
                      {i + 1}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              <div>{t("paperPlay.answered")} ({counts.answered})</div>
              <div className="text-destructive">{t("paperPlay.wrong")} ({counts.wrong})</div>
              <div>{t("paperPlay.unanswered")} ({counts.unanswered})</div>
              <div className="text-amber-500">{t("paperPlay.flagged")} ({counts.flagged})</div>
            </div>
          </div>
        )}
        <div className="text-xs text-muted-foreground">{t("paperPlay.autoSave")}</div>
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
                <Badge variant="outline">
                  {enumLabel(t, "qType", q.question_type as never)}
                </Badge>
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
                  variant={sheet.flagged[q.position] ? "default" : "ghost"}
                  onClick={toggleFlag}
                >
                  {t("paperPlay.flag")}
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
                      className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${
                        reveal
                          ? "border-success bg-success/10"
                          : wrongPick
                            ? "border-destructive bg-destructive/10"
                            : chosen
                              ? "border-primary bg-primary/5"
                              : "hover:bg-accent"
                      }`}
                    >
                      <span className="mr-2 font-semibold">
                        {String.fromCharCode(65 + o.order_index)}.
                      </span>
                      {localizedText(mode, { en: o.content.en, zh: o.content.zh })}
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

            <div className="flex items-center justify-between pt-2">
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
              ) : null}
              <Button
                variant="outline"
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
    </div>
  );
}
