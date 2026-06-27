"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateExam } from "@/lib/api/exam";
import { useAuthStore } from "@/lib/auth-store";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { trackExam } from "./exam-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import { Clock, Forward, Check } from "lucide-react";
import type { ExamKind, LanguageMode } from "@/lib/api/types";

const LANGUAGE_MODES: LanguageMode[] = ["en", "zh", "bilingual"];

export function ExamStartForm() {
  const t = useT();
  const router = useRouter();
  const [kind, setKind] = useState<ExamKind>("fixed");
  const [count, setCount] = useState<string>("");
  const user = useAuthStore((s) => s.user);
  const [languageMode, setLanguageMode] = useState<LanguageMode>(
    user?.language_mode ?? "en",
  );
  const create = useCreateExam();

  function start() {
    const body =
      kind === "cat"
        ? { kind, language_mode: languageMode }
        : count.trim() === ""
          ? { kind, language_mode: languageMode }
          : { kind, count: Math.max(1, Number(count) || 0), language_mode: languageMode };
    create.mutate(body, {
      onSuccess: (s) => {
        trackExam(s.id);
        router.push(`/exam/sessions/${s.id}`);
      },
      onError: (e) => {
        if (e instanceof ApiError && e.status === 422) {
          toast.error(t("examStart.notEnough"));
        } else {
          toast.error(t("examStart.couldNotStart"));
        }
      },
    });
  }

  const startLabel = create.isPending
    ? t("examStart.starting")
    : kind === "cat"
      ? t("examStart.startCat")
      : t("examStart.startFixed");

  return (
    <div className="space-y-6">
      {/* Kind selector */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <KindCard
          selected={kind === "fixed"}
          onSelect={() => setKind("fixed")}
          title={t("examStart.fixedTitle")}
          icon={<Clock className="h-5 w-5" />}
          meta={t("examStart.fixedMeta")}
          description={t("examStart.fixedDesc")}
          selectedLabel={t("examStart.selected")}
        />
        <KindCard
          selected={kind === "cat"}
          onSelect={() => setKind("cat")}
          title={t("examStart.catTitle")}
          icon={<Forward className="h-5 w-5" />}
          meta={t("examStart.catMeta")}
          description={t("examStart.catDesc")}
          selectedLabel={t("examStart.selected")}
        />
      </div>

      {/* Confirm + start */}
      <Card>
        <CardHeader>
          <Eyebrow>{t("examStart.confirm")}</Eyebrow>
          <CardTitle>{t("examStart.configureStart")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="exam-language-mode">{t("examStart.languageMode")}</Label>
              <Select
                value={languageMode}
                onValueChange={(v) => setLanguageMode(v as LanguageMode)}
              >
                <SelectTrigger id="exam-language-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGE_MODES.map((m) => (
                    <SelectItem key={m} value={m}>
                      {t(`lang.${m}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t("examStart.languageHint")}</p>
            </div>

            {kind === "fixed" ? (
              <div className="space-y-2">
                <Label htmlFor="exam-count">{t("examStart.countLabel")}</Label>
                <Input
                  id="exam-count"
                  type="number"
                  min={1}
                  max={500}
                  placeholder={t("examStart.countPlaceholder")}
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">{t("examStart.countHint")}</p>
              </div>
            ) : (
              <div className="space-y-2">
                <Label>{t("examStart.duration")}</Label>
                <div className="flex h-10 items-center rounded-md border border-input bg-muted/40 px-3 text-sm text-muted-foreground">
                  {t("examStart.durationValue")}
                </div>
                <p className="text-xs text-muted-foreground">{t("examStart.durationHint")}</p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              {kind === "cat" ? t("examStart.footerCat") : t("examStart.footerFixed")}
            </p>
            <Button size="pill" onClick={start} disabled={create.isPending} className="sm:min-w-[180px]">
              {startLabel}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function KindCard({
  selected,
  onSelect,
  title,
  icon,
  meta,
  description,
  selectedLabel,
}: {
  selected: boolean;
  onSelect: () => void;
  title: string;
  icon: React.ReactNode;
  meta: string;
  description: string;
  selectedLabel: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "group relative flex flex-col items-start gap-3 rounded-lg border p-5 text-left transition-all",
        selected
          ? "border-primary ring-1 ring-primary shadow-card"
          : "border-border hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-card",
      )}
    >
      <div className="flex w-full items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "flex h-9 w-9 items-center justify-center rounded-full",
              selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
            )}
          >
            {icon}
          </span>
          <h3 className="font-semibold">{title}</h3>
        </div>
        {selected && (
          <Badge>
            <Check className="h-3 w-3" /> {selectedLabel}
          </Badge>
        )}
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{meta}</p>
      <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
    </button>
  );
}
