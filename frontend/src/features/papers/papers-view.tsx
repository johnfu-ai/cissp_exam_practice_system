"use client";

// Paper library (题库) — PRD v1.4 FR-PAPER-03: browse published papers and
// launch practice/exam sessions in one click. PRD v1.5 adds the resume list
// (FR-PAPER-12) and free-practice dataset banks such as OSG v10 (FR-PAPER-10).

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiJson } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useBanks, useInProgressSessions, usePapers } from "@/lib/api/papers";
import type { InProgressSession } from "@/lib/api/types";

const BANK_COUNTS = [10, 20, 50, 100, 200];

export function PapersView() {
  const t = useT();
  const router = useRouter();
  const { data, isLoading, isError } = usePapers();
  const banks = useBanks();
  const inProgress = useInProgressSessions();
  const [launching, setLaunching] = useState<string | null>(null);
  const [bankCount, setBankCount] = useState(20);

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

  function resumeTarget(item: InProgressSession) {
    const paper = item.paper_id ? `&paper=${item.paper_id}` : "";
    return `/paper-play/${item.session_id}?kind=${item.kind}${paper}`;
  }

  if (isLoading) {
    return (
      <div className="p-8">
        <Loading label={t("common.loading")} />
      </div>
    );
  }

  const papers = data?.items ?? [];
  const resumable = inProgress.data?.items ?? [];
  const freeBanks = (banks.data?.items ?? []).filter((b) => !b.has_papers);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <PageHeader
        eyebrow={t("papersPage.eyebrow")}
        title={t("papersPage.title")}
        description={t("papersPage.subtitle")}
      />
      {isError && <p className="text-sm text-destructive">{t("error.generic")}</p>}

      {resumable.length > 0 && (
        <section aria-label={t("papersPage.inProgressTitle")} className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t("papersPage.inProgressTitle")}
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {resumable.map((item) => (
              <Card key={item.session_id} className="flex items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={item.kind === "exam" ? "default" : "secondary"}>
                      {item.kind === "exam"
                        ? t("paperPlay.examMode")
                        : t("paperPlay.practiceMode")}
                    </Badge>
                    <span className="truncate text-sm font-medium">
                      {item.paper_name ?? item.dataset_name}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("papersPage.answeredOf", {
                      answered: item.answered,
                      total: item.total,
                    })}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => router.push(resumeTarget(item))}
                  aria-label={`${t("papersPage.resume")}: ${item.paper_name ?? item.dataset_name}`}
                >
                  {t("papersPage.resume")}
                </Button>
              </Card>
            ))}
          </div>
        </section>
      )}

      {!isError && papers.length === 0 && freeBanks.length === 0 && (
        <Card className="p-6 text-sm text-muted-foreground">
          {t("papersPage.empty")}
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {papers.map((p) => (
          <Card key={p.id} hover className="flex flex-col gap-3 p-5">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold leading-snug">{p.name}</h3>
              {p.domain_number != null && (
                <Badge variant="secondary">
                  {t("papersPage.domain", { number: p.domain_number })}
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span>{t("papersPage.questionCount", { count: p.question_count })}</span>
              {p.duration_minutes != null && (
                <span>{t("papersPage.duration", { minutes: p.duration_minutes })}</span>
              )}
              <span>{t("papersPage.score", { score: p.total_score })}</span>
              {p.attempts > 0 && (
                <span>
                  {t("papersPage.attempts", { count: p.attempts })}
                  {p.best_score != null &&
                    ` · ${t("papersPage.best", { score: p.best_score })}`}
                </span>
              )}
            </div>
            <div className="mt-auto flex gap-2 pt-2">
              <Button
                size="sm"
                disabled={launching !== null}
                onClick={() => start(p.id, "practice")}
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
                onClick={() => start(p.id, "exam")}
                aria-label={`${t("papersPage.startExam")}: ${p.name}`}
              >
                {launching === `${p.id}:exam`
                  ? t("papersPage.starting")
                  : t("papersPage.startExam")}
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
    </div>
  );
}
