"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuestions } from "@/lib/api/questions";
import { useDomains } from "@/lib/api/taxonomy";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { useT } from "@/lib/i18n/provider";
import { enumLabel } from "@/features/shared/enum-label";
import { statusLabel, statusVariant } from "./labels";
import type { QuestionStatus, QuestionType, QuestionFilters, LanguageCode } from "@/lib/api/types";

const ANY = "__any__";
const STATUSES: QuestionStatus[] = ["draft", "pending_review", "published", "needs_revision", "archived"];
const TYPES: QuestionType[] = ["single_choice", "multiple_choice", "true_false", "scenario", "ordering", "drag_drop", "hotspot"];

/** Compact badge label for a question's available languages. */
function langBadge(languages: LanguageCode[]): string {
  const hasEn = languages.includes("en");
  const hasZh = languages.includes("zh");
  if (hasEn && hasZh) return "EN+中";
  if (hasZh) return "中";
  if (hasEn) return "EN";
  return "—";
}

export function QuestionList() {
  const t = useT();
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [status, setStatus] = useState<QuestionStatus | null>(null);
  const [type, setType] = useState<QuestionType | null>(null);
  const [domainId, setDomainId] = useState<string | null>(null);
  const [missingLang, setMissingLang] = useState<LanguageCode | null>(null);
  const [page, setPage] = useState(1);
  const size = 20;

  const domains = useDomains();
  const filters: QuestionFilters = {
    page,
    size,
    ...(search ? { search } : {}),
    ...(status ? { status } : {}),
    ...(type ? { question_type: type } : {}),
    ...(domainId ? { domain_id: domainId } : {}),
    ...(missingLang ? { missing_language: missingLang } : {}),
  };
  const list = useQuestions(filters);

  function resetPageAnd(fn: () => void) {
    setPage(1);
    fn();
  }

  const totalPages = list.data ? Math.max(1, Math.ceil(list.data.total / size)) : 1;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <form
              className="flex items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                resetPageAnd(() => setSearch(searchInput.trim()));
              }}
            >
              <Input
                placeholder={t("questionsList.searchPlaceholder")}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-56"
              />
              <Button type="submit" variant="outline" size="sm">{t("questionsList.search")}</Button>
            </form>

            <Select value={status ?? ANY} onValueChange={(v) => resetPageAnd(() => setStatus(v === ANY ? null : (v as QuestionStatus)))}>
              <SelectTrigger className="w-44"><SelectValue placeholder={t("questionsList.anyStatus")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("questionsList.anyStatus")}</SelectItem>
                {STATUSES.map((s) => <SelectItem key={s} value={s}>{statusLabel(t, s)}</SelectItem>)}
              </SelectContent>
            </Select>

            <Select value={type ?? ANY} onValueChange={(v) => resetPageAnd(() => setType(v === ANY ? null : (v as QuestionType)))}>
              <SelectTrigger className="w-44"><SelectValue placeholder={t("questionsList.anyType")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("questionsList.anyType")}</SelectItem>
                {TYPES.map((ty) => <SelectItem key={ty} value={ty}>{enumLabel(t, "qType", ty)}</SelectItem>)}
              </SelectContent>
            </Select>

            <Select value={domainId ?? ANY} onValueChange={(v) => resetPageAnd(() => setDomainId(v === ANY ? null : v))}>
              <SelectTrigger className="w-52"><SelectValue placeholder={t("questionsList.anyDomain")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("questionsList.anyDomain")}</SelectItem>
                {domains.data?.map((d) => <SelectItem key={d.id} value={d.id}>{d.number}. {d.name}</SelectItem>)}
              </SelectContent>
            </Select>

            <Select value={missingLang ?? ANY} onValueChange={(v) => resetPageAnd(() => setMissingLang(v === ANY ? null : (v as LanguageCode)))}>
              <SelectTrigger className="w-48"><SelectValue placeholder={t("questionsList.missingLang")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("questionsList.missingLangAny")}</SelectItem>
                <SelectItem value="en">{t("questionsList.missingEn")}</SelectItem>
                <SelectItem value="zh">{t("questionsList.missingZh")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {list.isLoading && <Loading label={t("questionsList.loadingQuestions")} />}
      {list.isError && <ErrorState message={t("questionsList.loadFailed")} onRetry={() => list.refetch()} />}
      {list.data && list.data.items.length === 0 && (
        <EmptyState title={t("questionsList.noQuestions")} description={t("questionsList.noQuestionsDesc")} />
      )}

      {list.data && list.data.items.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="px-4 py-2 font-medium">{t("questionsList.colQuestion")}</th>
                    <th className="px-4 py-2 font-medium">{t("questionsList.colType")}</th>
                    <th className="px-4 py-2 font-medium">{t("questionsList.colStatus")}</th>
                    <th className="px-4 py-2 font-medium">{t("questionsList.colDiff")}</th>
                    <th className="px-4 py-2 font-medium">{t("questionsList.colLanguages")}</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((q) => (
                    <tr key={q.id} className="border-b last:border-0 transition-colors hover:bg-accent/40">
                      <td className="px-4 py-2">
                        <Link href={`/questions/${q.id}`} className="font-mono text-xs hover:underline">#{q.id.slice(0, 8)}</Link>
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{enumLabel(t, "qType", q.question_type)}</td>
                      <td className="px-4 py-2"><Badge variant={statusVariant(q.status)}>{statusLabel(t, q.status)}</Badge></td>
                      <td className="px-4 py-2 text-muted-foreground">{q.difficulty ?? "—"}</td>
                      <td className="px-4 py-2"><Badge variant="outline">{langBadge(q.available_languages)}</Badge></td>
                      <td className="px-4 py-2 text-right">
                        <Button asChild variant="ghost" size="sm"><Link href={`/questions/${q.id}`}>{t("questionsList.open")}</Link></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {list.data && list.data.total > size && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {t("questionsList.pagination", { total: list.data.total, page, totalPages })}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>{t("common.previous")}</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>{t("common.next")}</Button>
          </div>
        </div>
      )}
    </div>
  );
}
