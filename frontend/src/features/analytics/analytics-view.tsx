"use client";

import { useState } from "react";
import {
  useDomainMastery,
  useTrend,
  useWeakAreas,
  useErrorTypes,
} from "@/lib/api/analytics";
import { PageHeader } from "@/components/page-header";
import { Eyebrow } from "@/components/eyebrow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { useT } from "@/lib/i18n/provider";
import type { TrendPoint } from "@/lib/api/types";
import {
  fmtPct,
  fmtDuration,
  errorTypeLabel,
  accuracyColor,
  MASTERY_LABELS,
  MASTERY_CLASSES,
} from "./format";

function Sparkline({ points, ariaLabel }: { points: TrendPoint[]; ariaLabel: string }) {
  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">{ariaLabel}</p>;
  }
  const W = 600;
  const H = 120;
  const pad = 8;
  const n = points.length;
  const x = (i: number) => (n === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1));
  const y = (acc: number) => H - pad - acc * (H - 2 * pad);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.accuracy)}`).join(" ");
  const areaPath = `${path} L${x(n - 1)},${H - pad} L${x(0)},${H - pad} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-32 w-full" preserveAspectRatio="none" role="img" aria-label={ariaLabel}>
      <line x1={pad} y1={y(0.7)} x2={W - pad} y2={y(0.7)} stroke="currentColor" strokeDasharray="4 4" className="text-muted-foreground/40" />
      <path d={areaPath} className="fill-primary/10" />
      <path d={path} fill="none" stroke="currentColor" strokeWidth={2} className="text-primary" />
      {points.map((p, i) => (
        <circle key={p.date} cx={x(i)} cy={y(p.accuracy)} r={3} className="fill-primary" />
      ))}
    </svg>
  );
}

export function AnalyticsView() {
  const t = useT();
  const [window, setWindow] = useState<30 | 90>(30);
  const domains = useDomainMastery();
  const trend = useTrend(window);
  const weak = useWeakAreas();
  const errors = useErrorTypes();

  if (domains.isLoading) return <Loading label={t("analytics.loadingAnalytics")} />;
  if (domains.isError) {
    return <ErrorState message={t("analytics.loadFailed")} onRetry={() => domains.refetch()} />;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow={t("analytics.eyebrow")}
        title={t("analytics.title")}
        description={t("analytics.description")}
      />

      <Eyebrow className="mb-3">{t("analytics.performance")}</Eyebrow>
      <Card className="mb-8">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{t("analytics.accuracyTrend")}</CardTitle>
          <div className="flex gap-1">
            {([30, 90] as const).map((w) => (
              <Button
                key={w}
                variant={window === w ? "default" : "outline"}
                size="sm"
                onClick={() => setWindow(w)}
              >
                {t("analytics.days", { w })}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {trend.isLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : (
            <Sparkline points={trend.data?.points ?? []} ariaLabel={t("analytics.noActivityWindow")} />
          )}
        </CardContent>
      </Card>

      <Eyebrow className="mb-3">{t("analytics.mastery")}</Eyebrow>
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>{t("analytics.domainMastery")}</CardTitle>
        </CardHeader>
        <CardContent>
          {domains.data && domains.data.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("analytics.noBlueprint")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{t("analytics.colDomain")}</th>
                    <th className="py-2 pr-4 font-medium">{t("analytics.colWeight")}</th>
                    <th className="py-2 pr-4 font-medium">{t("analytics.colAnswered")}</th>
                    <th className="py-2 pr-4 font-medium">{t("analytics.colAccuracy")}</th>
                    <th className="py-2 pr-4 font-medium">{t("analytics.colAvgTime")}</th>
                    <th className="py-2 font-medium">{t("analytics.colMastery")}</th>
                  </tr>
                </thead>
                <tbody>
                  {domains.data?.map((m) => (
                    <tr key={m.domain_id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        {m.number}. {m.name}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">{m.weight_pct}%</td>
                      <td className="py-2 pr-4">{m.answered}</td>
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2">
                          <span className="w-10">{m.answered === 0 ? "—" : fmtPct(m.accuracy)}</span>
                          <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-muted sm:block">
                            <div className={`h-full ${accuracyColor(m.accuracy)}`} style={{ width: `${Math.round(m.accuracy * 100)}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {m.answered === 0 ? "—" : fmtDuration(m.avg_time_ms)}
                      </td>
                      <td className="py-2">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${MASTERY_CLASSES[m.mastery_level]}`}>
                          {MASTERY_LABELS[m.mastery_level]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Eyebrow className="mb-3">{t("analytics.focusAreas")}</Eyebrow>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("analytics.weakKp")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {weak.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
            {weak.data && weak.data.weak_knowledge_points.length === 0 && (
              <p className="text-sm text-muted-foreground">{t("analytics.noWeakKp")}</p>
            )}
            {weak.data?.weak_knowledge_points.map((w) => (
              <div key={w.knowledge_point_id ?? w.label} className="flex items-center justify-between text-sm">
                <span>{w.label}</span>
                <span className="text-muted-foreground">
                  {fmtPct(w.accuracy)} ({w.correct}/{w.answered})
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("analytics.errorTypes")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {errors.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
            {errors.data && errors.data.distribution.length === 0 && (
              <p className="text-sm text-muted-foreground">{t("analytics.noWrongRecorded")}</p>
            )}
            {errors.data?.distribution.map((e) => (
              <div key={e.error_type ?? "unclassified"} className="flex items-center justify-between text-sm">
                <span>{errorTypeLabel(e.error_type)}</span>
                <span className="text-muted-foreground">{e.count}</span>
              </div>
            ))}
            {errors.data && errors.data.total_wrong_classified > 0 && (
              <p className="pt-2 text-xs text-muted-foreground">
                {t("analytics.wrongClassified", { n: errors.data.total_wrong_classified })}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
