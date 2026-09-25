"use client";

// Paper library (题库) — PRD v1.4 FR-PAPER-03: browse published papers and
// launch practice/exam sessions in one click. PRD v1.5 added free-practice
// dataset banks (FR-PAPER-10). PRD v1.6 restyles the page after the mock-paper
// reference (stats row, attempt status on cards) and replaces the dedicated
// "in progress" section with a continue-or-new prompt on session start
// (FR-PAPER-12) plus an answer-records modal per paper (FR-PAPER-14).

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TriangleAlert } from "lucide-react";
import { apiJson } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import {
  useBanks,
  useInProgressSessions,
  usePaperSessions,
  usePapers,
} from "@/lib/api/papers";
import { useWrongBook } from "@/lib/api/wrong-book";
import type { InProgressSession, PaperListItem } from "@/lib/api/types";
import { formatClock } from "@/features/paper-play/answer-sheet";

const BANK_COUNTS = [10, 20, 50, 100, 200];

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function PapersView() {
  const t = useT();
  const router = useRouter();
  const { data, isLoading, isError } = usePapers();
  const banks = useBanks();
  const inProgress = useInProgressSessions();
  const wrongBook = useWrongBook("wrong", null);
  const [launching, setLaunching] = useState<string | null>(null);
  const [bankCount, setBankCount] = useState(20);
  // FR-PAPER-12: continue-or-new prompt target (paper + mode + the detected
  // in-progress session)
  const [prompt, setPrompt] = useState<{
    paper: PaperListItem;
    mode: "practice" | "exam";
    existing: InProgressSession;
  } | null>(null);
  // FR-PAPER-14: answer-records modal target
  const [recordsFor, setRecordsFor] = useState<PaperListItem | null>(null);

  async function start(paperId: string, mode: "practice" | "exam") {
    const key = `${paperId}:${mode}`;
    setLaunching(key);
    try {
      const session = await apiJson<{ id: string }>(`/api/papers/${paperId}/sessions`, {
        method: "POST",
        body: JSON.stringify({ mode }),
      });
      router.push(`/paper-play/${session.id}?kind=${mode}&paper=${paperId}`);
    } catch {
      setLaunching(null);
    }
  }

  // FR-PAPER-12: entering practice/exam with an in-progress session for the
  // SAME paper+mode prompts 继续上次答题 vs 重新开始 instead of listing the
  // sessions in a dedicated section.
  function startOrPrompt(paper: PaperListItem, mode: "practice" | "exam") {
    if (launching !== null) return;
    const existing = (inProgress.data?.items ?? [])
      .filter((i) => i.paper_id === paper.id && i.kind === mode)
      .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""))[0];
    if (existing) {
      setPrompt({ paper, mode, existing });
      return;
    }
    void start(paper.id, mode);
  }

  async function startBank(datasetSlug: string, orderMode: "sequential" | "random") {
    const key = `${datasetSlug}:${orderMode}`;
    setLaunching(key);
    try {
      const session = await apiJson<{ id: string }>("/api/practice/sessions", {
        method: "POST",
        body: JSON.stringify({
          dataset_slug: datasetSlug,
          count: bankCount,
          order_mode: orderMode,
        }),
      });
      router.push(`/paper-play/${session.id}?kind=practice`);
    } catch {
      setLaunching(null);
    }
  }

  if (isLoading) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  const papers = data?.items ?? [];
  const freeBanks = (banks.data?.items ?? []).filter((b) => !b.has_papers);
  const completedCount = papers.filter((p) => p.attempts > 0).length;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <PageHeader
        eyebrow={t("papersPage.eyebrow")}
        title={t("papersPage.title")}
        description={t("papersPage.subtitle")}
      />
      {isError && <p className="text-sm text-destructive">{t("error.generic")}</p>}

      {/* paper-style stats row (FR-PAPER-03, v1.6) */}
      <div className="grid grid-cols-3 gap-3" data-testid="papers-stats">
        <Card className="p-4 text-center">
          <div className="text-2xl font-semibold tabular-nums">{papers.length}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t("papersPage.statsPapers")}
          </div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-semibold tabular-nums">{completedCount}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t("papersPage.statsCompleted")}
          </div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-semibold tabular-nums">
            {wrongBook.data?.total ?? 0}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t("papersPage.statsWrong")}
          </div>
        </Card>
      </div>

      {!isError && papers.length === 0 && freeBanks.length === 0 && (
        <Card className="p-6 text-sm text-muted-foreground">
          {t("papersPage.empty")}
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2" data-testid="papers-grid">
        {papers.map((p) => (
          <Card key={p.id} hover className="flex flex-col gap-3 p-5">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold leading-snug">{p.name}</h3>
              {p.attempts > 0 ? (
                <Badge className="border-0 bg-success/10 text-success">
                  {t("papersPage.attemptedTimes", { count: p.attempts })}
                </Badge>
              ) : (
                <Badge variant="secondary">{t("papersPage.notAttempted")}</Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {p.duration_minutes != null && (
                <span>{t("papersPage.duration", { minutes: p.duration_minutes })}</span>
              )}
              <span>{t("papersPage.score", { score: p.total_score })}</span>
              <span>{t("papersPage.questionCount", { count: p.question_count })}</span>
              {p.best_score != null && (
                <span className="font-medium text-foreground">
                  {t("papersPage.best", { score: p.best_score })}
                </span>
              )}
            </div>
            <div className="mt-auto flex flex-wrap gap-2 pt-2">
              <Button
                size="sm"
                disabled={launching !== null}
                onClick={() => startOrPrompt(p, "practice")}
                aria-label={`${t("papersPage.startPractice")}: ${p.name}`}
              >
                {launching === `${p.id}:practice`
                  ? t("papersPage.starting")
                  : t("papersPage.startPractice")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={launching !== null}
                onClick={() => startOrPrompt(p, "exam")}
                aria-label={`${t("papersPage.startExam")}: ${p.name}`}
              >
                {launching === `${p.id}:exam`
                  ? t("papersPage.starting")
                  : t("papersPage.startExam")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setRecordsFor(p)}
                aria-label={`${t("papersPage.records")}: ${p.name}`}
              >
                {t("papersPage.records")}
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {freeBanks.length > 0 && (
        <section aria-label={t("papersPage.banksTitle")} className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t("papersPage.banksTitle")}
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {freeBanks.map((b) => (
              <Card key={b.dataset_slug} hover className="flex flex-col gap-3 p-5">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold leading-snug">{b.name}</h3>
                  <Badge variant="outline">{b.dataset_slug}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {t("papersPage.questionCount", { count: b.question_count })}
                </p>
                <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
                  <Select
                    value={String(bankCount)}
                    onValueChange={(v) => setBankCount(Number(v))}
                  >
                    <SelectTrigger
                      className="w-28"
                      aria-label={t("papersPage.questionsPerSession")}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {BANK_COUNTS.map((n) => (
                        <SelectItem key={n} value={String(n)}>
                          {n}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    disabled={launching !== null}
                    onClick={() => startBank(b.dataset_slug, "sequential")}
                    aria-label={`${t("papersPage.sequential")}: ${b.name}`}
                  >
                    {launching === `${b.dataset_slug}:sequential`
                      ? t("papersPage.starting")
                      : t("papersPage.sequential")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={launching !== null}
                    onClick={() => startBank(b.dataset_slug, "random")}
                    aria-label={`${t("papersPage.random")}: ${b.name}`}
                  >
                    {launching === `${b.dataset_slug}:random`
                      ? t("papersPage.starting")
                      : t("papersPage.random")}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* FR-PAPER-12: continue-or-new prompt (mock-paper 继续答题 dialog) */}
      <Dialog
        open={prompt !== null}
        onOpenChange={(open) => {
          if (!open) setPrompt(null);
        }}
      >
        <DialogContent className="max-w-md" data-testid="continue-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <TriangleAlert className="h-5 w-5 text-amber-500" aria-hidden />
              {t("papersPage.continueTitle")}
            </DialogTitle>
            <DialogDescription>{t("papersPage.continuePrompt")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                const p = prompt;
                setPrompt(null);
                if (p) void start(p.paper.id, p.mode);
              }}
            >
              {t("papersPage.startOver")}
            </Button>
            <Button
              onClick={() => {
                const p = prompt;
                setPrompt(null);
                if (!p) return;
                router.push(
                  `/paper-play/${p.existing.session_id}?kind=${p.existing.kind}&paper=${p.paper.id}`,
                );
              }}
            >
              {t("papersPage.continueLast")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* FR-PAPER-14: answer-records modal (mock-paper 做题记录) */}
      <RecordsDialog paper={recordsFor} onClose={() => setRecordsFor(null)} />
    </div>
  );
}

function RecordsDialog({
  paper,
  onClose,
}: {
  paper: PaperListItem | null;
  onClose: () => void;
}) {
  const t = useT();
  const sessions = usePaperSessions(paper?.id ?? null);

  const items = sessions.data?.items ?? [];
  const examScores = items
    .filter((i) => i.kind === "exam" && i.score != null)
    .map((i) => i.score as number);
  const best = examScores.length ? Math.max(...examScores) : null;
  const lowest = examScores.length ? Math.min(...examScores) : null;
  const average =
    examScores.length > 0
      ? Math.round(examScores.reduce((a, b) => a + b, 0) / examScores.length)
      : null;

  return (
    <Dialog
      open={paper !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-w-3xl" data-testid="records-dialog">
        <DialogHeader>
          <DialogTitle>
            {paper ? `${paper.name} · ${t("papersPage.records")}` : ""}
          </DialogTitle>
        </DialogHeader>
        {sessions.isLoading ? (
          <div className="py-6">
            <Loading label={t("common.loading")} />
          </div>
        ) : items.length === 0 ? (
          <p className="py-6 text-sm text-muted-foreground">
            {t("papersPage.noRecords")}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-4 gap-2">
              {(
                [
                  ["recordsExamAttempts", examScores.length],
                  ["recordsBest", best],
                  ["recordsLowest", lowest],
                  ["recordsAverage", average],
                ] as const
              ).map(([key, value]) => (
                <Card key={key} className="p-3 text-center">
                  <div className="text-xl font-semibold tabular-nums">
                    {value ?? "—"}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {t(`papersPage.${key}`)}
                  </div>
                </Card>
              ))}
            </div>
            <div className="max-h-[50vh] overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-2 font-medium">{t("papersPage.colTime")}</th>
                    <th className="py-2 pr-2 font-medium">{t("papersPage.colDuration")}</th>
                    <th className="py-2 pr-2 font-medium">{t("papersPage.colScore")}</th>
                    <th className="py-2 pr-2 font-medium">{t("papersPage.colCorrect")}</th>
                    <th className="py-2 pr-2 font-medium">{t("papersPage.colTotal")}</th>
                    <th className="py-2 pr-2 font-medium">{t("papersPage.colStatus")}</th>
                    <th className="py-2 font-medium">{t("papersPage.colDetail")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id} className="border-b last:border-0">
                      <td className="py-2 pr-2 tabular-nums">{formatTime(row.started_at)}</td>
                      <td className="py-2 pr-2 tabular-nums">
                        {row.duration_seconds != null
                          ? formatClock(row.duration_seconds * 1000)
                          : "—"}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {row.score != null && row.max_score != null
                          ? `${row.score}/${row.max_score}`
                          : "—"}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">{row.correct_count}</td>
                      <td className="py-2 pr-2 tabular-nums">{row.total_questions}</td>
                      <td className="py-2 pr-2">
                        {row.kind === "practice" ? (
                          <span className="text-muted-foreground">
                            {t("papersPage.statusPractice")}
                          </span>
                        ) : row.status === "in_progress" ? (
                          <span className="text-amber-600">
                            {t("papersPage.statusInProgress")}
                          </span>
                        ) : row.passed === true ? (
                          <span className="text-success">{t("papersPage.statusPassed")}</span>
                        ) : row.passed === false ? (
                          <span className="text-destructive">
                            {t("papersPage.statusFailed")}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2">
                        {row.kind === "exam" && row.status !== "in_progress" ? (
                          <Link
                            className="text-primary underline-offset-2 hover:underline"
                            href={`/paper-play/${row.id}/report`}
                          >
                            {t("papersPage.detail")}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
