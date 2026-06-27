"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Target,
  ListChecks,
  Clock,
  Flame,
  PenLine,
  FileText,
  RotateCcw,
  ArrowRight,
} from "lucide-react";
import {
  useDashboard,
  useWeakAreas,
  useRecommendation,
  useDomainMastery,
} from "@/lib/api/analytics";
import { PageHeader } from "@/components/page-header";
import { Eyebrow } from "@/components/eyebrow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { useT } from "@/lib/i18n/provider";
import { fmtPct, fmtDuration, fmtDate, accuracyColor } from "./format";

function KpiCard({
  icon: Icon,
  label,
  value,
  delta,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  delta?: React.ReactNode;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="mt-0.5 text-2xl font-semibold tabular-nums">{value}</p>
          {delta && <div className="mt-0.5 text-xs text-muted-foreground">{delta}</div>}
        </div>
      </div>
    </Card>
  );
}

function ContinueCard({
  href,
  icon: Icon,
  title,
  description,
  cta,
}: {
  href: string;
  icon: LucideIcon;
  title: string;
  description: string;
  cta: string;
}) {
  return (
    <Card hover className="flex flex-col overflow-hidden">
      <div className="flex aspect-[4/3] items-center justify-center bg-gradient-to-br from-secondary to-accent">
        <Icon className="h-10 w-10 text-primary" />
      </div>
      <div className="flex flex-1 flex-col p-4">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        <Button
          asChild
          variant="link"
          className="mt-3 h-auto justify-start p-0 text-primary"
        >
          <Link href={href}>
            {cta}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    </Card>
  );
}

export function Dashboard() {
  const t = useT();
  const dashboard = useDashboard();
  const weak = useWeakAreas();
  const rec = useRecommendation();
  const domains = useDomainMastery();

  if (dashboard.isLoading) return <Loading label={t("dashboard.loadingDashboard")} />;
  if (dashboard.isError || !dashboard.data) {
    return <ErrorState message={t("dashboard.loadFailed")} onRetry={() => dashboard.refetch()} />;
  }
  const d = dashboard.data;
  const fresh = d.total_answered === 0;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow={t("dashboard.eyebrow")}
        title={t("dashboard.title")}
        description={t("dashboard.description")}
        actions={
          <Button asChild>
            <Link href="/practice">{t("dashboard.continuePractice")}</Link>
          </Button>
        }
      />

      {fresh ? (
        <Card>
          <CardContent className="py-10 text-center">
            <h3 className="text-base font-medium">{t("dashboard.noActivity")}</h3>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
              {t("dashboard.noActivityDesc")}
            </p>
            <Button asChild className="mt-4">
              <Link href="/practice">{t("dashboard.startPracticing")}</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* KPI grid */}
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              icon={Target}
              label={t("dashboard.accuracy")}
              value={fmtPct(d.accuracy)}
              delta={
                <span className="tabular-nums">
                  {t("dashboard.correctOf", { c: d.correct_count, a: d.total_answered })}
                </span>
              }
            />
            <KpiCard
              icon={ListChecks}
              label={t("dashboard.answered")}
              value={`${d.correct_count}/${d.total_answered}`}
            />
            <KpiCard
              icon={Clock}
              label={t("dashboard.studyTime")}
              value={fmtDuration(d.study_time_ms)}
            />
            <KpiCard
              icon={Flame}
              label={t("dashboard.streak")}
              value={t("dashboard.streakDays", { n: d.streak_days })}
              delta={<>{t("dashboard.lastActive", { date: fmtDate(d.last_active_at) })}</>}
            />
          </div>

          {/* Continue section */}
          <section className="mb-8">
            <Eyebrow className="mb-3">{t("dashboard.continue")}</Eyebrow>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <ContinueCard
                href="/practice"
                icon={PenLine}
                title={t("dashboard.practiceTitle")}
                description={t("dashboard.practiceDesc")}
                cta={t("dashboard.startPracticeCta")}
              />
              <ContinueCard
                href="/exam"
                icon={FileText}
                title={t("dashboard.mockExamTitle")}
                description={t("dashboard.mockExamDesc")}
                cta={t("dashboard.startExamCta")}
              />
              <ContinueCard
                href="/review"
                icon={RotateCcw}
                title={t("dashboard.reviewTitle")}
                description={t("dashboard.reviewDesc")}
                cta={t("dashboard.reviewCta")}
              />
            </div>
          </section>

          {/* Weak domains + recommendation */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>{t("dashboard.weakDomains")}</CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/analytics">{t("dashboard.viewAll")}</Link>
                </Button>
              </CardHeader>
              <CardContent className="space-y-3">
                {weak.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
                {weak.data && weak.data.weak_domains.length === 0 && (
                  <p className="text-sm text-muted-foreground">{t("dashboard.noWeakDomains")}</p>
                )}
                {weak.data?.weak_domains.map((w) => (
                  <div key={w.domain_id ?? w.label} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span>{w.label}</span>
                      <span className="text-muted-foreground">
                        {fmtPct(w.accuracy)} ({w.correct}/{w.answered})
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className={`h-full ${accuracyColor(w.accuracy)}`}
                        style={{ width: `${Math.round(w.accuracy * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("dashboard.todayRec")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {rec.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
                {rec.data && (
                  <>
                    <p className="text-sm">{rec.data.rationale}</p>
                    <div className="flex flex-wrap gap-2 text-xs">
                      {rec.data.focus_domain && (
                        <Badge variant="secondary">
                          {t("dashboard.focus", { label: rec.data.focus_domain.label })}
                        </Badge>
                      )}
                      <Badge variant="outline">
                        {t("dashboard.toReview", { n: rec.data.wrong_to_review.length })}
                      </Badge>
                      <Badge variant="outline">
                        {t("dashboard.suggested", { n: rec.data.next_practice_question_ids.length })}
                      </Badge>
                    </div>
                    <div className="flex gap-2">
                      <Button asChild size="sm">
                        <Link href="/review">{t("dashboard.reviewWrong")}</Link>
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Domain mastery */}
          <Card className="mt-6">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{t("dashboard.domainMastery")}</CardTitle>
              <span className="text-xs text-muted-foreground">
                {t("dashboard.lastActive", { date: fmtDate(d.last_active_at) })}
              </span>
            </CardHeader>
            <CardContent className="space-y-3">
              {domains.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
              {domains.data && domains.data.length === 0 && (
                <p className="text-sm text-muted-foreground">{t("dashboard.noBlueprint")}</p>
              )}
              {domains.data?.map((m) => (
                <div key={m.domain_id} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span>
                      {m.number}. {m.name}
                    </span>
                    <span className="text-muted-foreground">
                      {m.answered === 0 ? "—" : `${fmtPct(m.accuracy)} (${m.correct}/${m.answered})`}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full ${accuracyColor(m.accuracy)}`}
                      style={{ width: `${Math.round(m.accuracy * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
