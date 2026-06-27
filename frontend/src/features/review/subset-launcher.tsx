"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RotateCcw, Bookmark, Flag, type LucideIcon } from "lucide-react";
import { useDomains } from "@/lib/api/taxonomy";
import { useCreateSession } from "@/lib/api/practice";
import { ApiError } from "@/lib/api";
import { trackSession } from "@/features/practice/session-tracker";
import { Card, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { useT } from "@/lib/i18n/provider";
import type { Subset, SessionCreateInput } from "@/lib/api/types";

const ANY = "__any__";

const SUBSET_ICON: Partial<Record<Subset, LucideIcon>> = {
  wrong: RotateCcw,
  bookmarked: Bookmark,
  needs_review: Flag,
};

/**
 * Launches a scoped re-practice session over a question subset
 * (wrong / bookmarked / needs_review). Backed by the existing
 * POST /api/practice/sessions API — no dedicated browse endpoint exists.
 */
export function SubsetLauncher({
  subset,
  title,
  description,
  emptyHint,
}: {
  subset: Subset;
  title: string;
  description: string;
  emptyHint: string;
}) {
  const router = useRouter();
  const t = useT();
  const [count, setCount] = useState(10);
  const [domainId, setDomainId] = useState<string | null>(null);
  const domains = useDomains();
  const create = useCreateSession();
  const Icon = SUBSET_ICON[subset] ?? RotateCcw;

  function start() {
    const payload: SessionCreateInput = { count, subset, order_mode: "random" };
    if (domainId) payload.domain_id = domainId;
    create.mutate(payload, {
      onSuccess: (s) => {
        trackSession(s.id);
        router.push(`/practice/sessions/${s.id}`);
      },
      onError: (e) => {
        if (e instanceof ApiError && e.status === 422) {
          toast.error(emptyHint);
        } else {
          toast.error(t("subsetLauncher.couldNotStart"));
        }
      },
    });
  }

  return (
    <Card hover className="overflow-hidden">
      <div className="flex items-center gap-4 bg-gradient-to-br from-secondary to-accent p-5">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-background text-primary shadow-sm">
          <Icon className="h-6 w-6" />
        </div>
        <div className="min-w-0">
          <Eyebrow className="mb-1">{t("subsetLauncher.rePractice")}</Eyebrow>
          <CardTitle className="text-xl">{title}</CardTitle>
        </div>
      </div>
      <div className="space-y-4 p-6">
        <p className="text-sm text-muted-foreground">{description}</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={`count-${subset}`}>{t("subsetLauncher.questionCount")}</Label>
            <Input
              id={`count-${subset}`}
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("subsetLauncher.domainOptional")}</Label>
            <Select
              value={domainId ?? ANY}
              onValueChange={(v) => setDomainId(v === ANY ? null : v)}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("subsetLauncher.allDomains")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("subsetLauncher.allDomains")}</SelectItem>
                {domains.data?.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.number}. {d.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button size="pill" onClick={start} disabled={create.isPending}>
          {create.isPending ? t("subsetLauncher.starting") : t("subsetLauncher.startReview")}
        </Button>
      </div>
    </Card>
  );
}
