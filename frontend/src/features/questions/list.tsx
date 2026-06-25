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
import { STATUS_LABELS, statusVariant } from "./labels";
import type { QuestionStatus, QuestionType, QuestionFilters } from "@/lib/api/types";

const ANY = "__any__";
const STATUSES: QuestionStatus[] = ["draft", "pending_review", "published", "needs_revision", "archived"];
const TYPES: QuestionType[] = ["single_choice", "multiple_choice", "true_false", "scenario", "ordering", "drag_drop", "hotspot"];

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function QuestionList() {
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [status, setStatus] = useState<QuestionStatus | null>(null);
  const [type, setType] = useState<QuestionType | null>(null);
  const [domainId, setDomainId] = useState<string | null>(null);
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
  };
  const list = useQuestions(filters);

  function resetPageAnd(fn: () => void) {
    setPage(1);
    fn();
  }

  const totalPages = list.data ? Math.max(1, Math.ceil(list.data.total / size)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            resetPageAnd(() => setSearch(searchInput.trim()));
          }}
        >
          <Input
            placeholder="Search stem…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-56"
          />
          <Button type="submit" variant="outline">Search</Button>
        </form>

        <Select value={status ?? ANY} onValueChange={(v) => resetPageAnd(() => setStatus(v === ANY ? null : (v as QuestionStatus)))}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Any status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any status</SelectItem>
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{STATUS_LABELS[s]}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={type ?? ANY} onValueChange={(v) => resetPageAnd(() => setType(v === ANY ? null : (v as QuestionType)))}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Any type" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any type</SelectItem>
            {TYPES.map((t) => <SelectItem key={t} value={t}>{labelize(t)}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={domainId ?? ANY} onValueChange={(v) => resetPageAnd(() => setDomainId(v === ANY ? null : v))}>
          <SelectTrigger className="w-52"><SelectValue placeholder="Any domain" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any domain</SelectItem>
            {domains.data?.map((d) => <SelectItem key={d.id} value={d.id}>{d.number}. {d.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {list.isLoading && <Loading label="Loading questions…" />}
      {list.isError && <ErrorState message="Could not load questions." onRetry={() => list.refetch()} />}
      {list.data && list.data.items.length === 0 && (
        <EmptyState title="No questions found" description="Adjust your filters or import a dataset." />
      )}

      {list.data && list.data.items.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Stem</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Diff.</th>
                  <th className="px-4 py-2 font-medium">Lang</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((q) => (
                  <tr key={q.id} className="border-b last:border-0 hover:bg-accent/40">
                    <td className="max-w-md truncate px-4 py-2">
                      <Link href={`/questions/${q.id}`} className="hover:underline">{q.stem}</Link>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{labelize(q.question_type)}</td>
                    <td className="px-4 py-2"><Badge variant={statusVariant(q.status)}>{STATUS_LABELS[q.status]}</Badge></td>
                    <td className="px-4 py-2 text-muted-foreground">{q.difficulty ?? "—"}</td>
                    <td className="px-4 py-2 text-muted-foreground">{q.language}</td>
                    <td className="px-4 py-2 text-right">
                      <Button asChild variant="ghost" size="sm"><Link href={`/questions/${q.id}`}>Open</Link></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {list.data && list.data.total > size && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {list.data.total} questions · page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  );
}
