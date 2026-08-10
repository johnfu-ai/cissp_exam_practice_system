"use client";

import { useState } from "react";
import {
  useMappings, useCreateMapping, useUpdateMapping, useDeleteMapping,
} from "@/lib/api/etl";
import { useDomains } from "@/lib/api/taxonomy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { Trash2 } from "lucide-react";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import type { ChapterDomainMapping } from "@/lib/api/types";

const NONE = "__none__";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

export function MappingsTab() {
  const t = useT();
  const [filterSlug, setFilterSlug] = useState("");
  const mappings = useMappings(filterSlug || null);
  const domains = useDomains();
  const create = useCreateMapping();
  const remove = useDeleteMapping();

  const [datasetSlug, setDatasetSlug] = useState("");
  const [chapterNumber, setChapterNumber] = useState("1");
  const [chapterTitle, setChapterTitle] = useState("");
  const [domainId, setDomainId] = useState<string | null>(null);
  const [pending, setPending] = useState<ChapterDomainMapping | null>(null);

  if (mappings.isLoading || domains.isLoading) return <Loading label={t("taxonomyMappings.loading")} />;
  if (mappings.isError) {
    return <ErrorState message={t("taxonomyMappings.loadFailed")} onRetry={() => mappings.refetch()} />;
  }

  const domainLabel = (id: string | null) => {
    if (!id) return t("taxonomyMappings.noDomain");
    const d = domains.data?.find((x) => x.id === id);
    return d ? `${d.number}. ${d.name}` : id;
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("taxonomyMappings.createTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="mapping-dataset">{t("taxonomyMappings.datasetSlug")}</Label>
            <Input
              id="mapping-dataset"
              value={datasetSlug}
              onChange={(e) => setDatasetSlug(e.target.value)}
              placeholder={t("taxonomyMappings.datasetSlugPlaceholder")}
              className="w-40"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="mapping-ch-num">{t("taxonomyMappings.chapterNumber")}</Label>
            <Input
              id="mapping-ch-num"
              type="number"
              min={1}
              value={chapterNumber}
              onChange={(e) => setChapterNumber(e.target.value)}
              className="w-24"
            />
          </div>
          <div className="min-w-[12rem] flex-1 space-y-1.5">
            <Label htmlFor="mapping-ch-title">{t("taxonomyMappings.chapterTitle")}</Label>
            <Input
              id="mapping-ch-title"
              value={chapterTitle}
              onChange={(e) => setChapterTitle(e.target.value)}
              placeholder={t("taxonomyMappings.chapterTitlePlaceholder")}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("taxonomyMappings.domain")}</Label>
            <Select value={domainId ?? NONE} onValueChange={(v) => setDomainId(v === NONE ? null : v)}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder={t("taxonomyMappings.noDomain")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>{t("taxonomyMappings.noDomain")}</SelectItem>
                {domains.data?.map((d) => (
                  <SelectItem key={d.id} value={d.id}>{d.number}. {d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            size="pill"
            disabled={create.isPending}
            onClick={() => {
              const slug = datasetSlug.trim();
              const num = Number(chapterNumber);
              const title = chapterTitle.trim();
              if (!slug || !title || !Number.isFinite(num) || num < 1) {
                toast.error(t("taxonomyMappings.toastRequired"));
                return;
              }
              create.mutate(
                { dataset_slug: slug, chapter_number: num, chapter_title: title, domain_id: domainId },
                {
                  onSuccess: () => {
                    setChapterTitle("");
                    toast.success(t("taxonomyMappings.toastAdded"));
                  },
                  onError: (e) => err(e, t("taxonomyMappings.couldNotAdd")),
                },
              );
            }}
          >
            {t("taxonomyMappings.add")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
          <CardTitle className="text-base">{t("taxonomyMappings.listTitle")}</CardTitle>
          <div className="flex items-center gap-2">
            <Label htmlFor="mapping-filter" className="sr-only">{t("taxonomyMappings.filterSlug")}</Label>
            <Input
              id="mapping-filter"
              value={filterSlug}
              onChange={(e) => setFilterSlug(e.target.value)}
              placeholder={t("taxonomyMappings.filterSlugPlaceholder")}
              className="w-40"
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {(mappings.data ?? []).length === 0 && (
            <p className="text-sm text-muted-foreground">{t("taxonomyMappings.noMappings")}</p>
          )}
          {(mappings.data ?? []).map((m) => (
            <MappingRow
              key={m.id}
              mapping={m}
              domainLabel={domainLabel(m.domain_id)}
              domains={domains.data ?? []}
              onDelete={() => setPending(m)}
            />
          ))}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!pending}
        onOpenChange={(o) => !o && setPending(null)}
        title={t("taxonomyMappings.deleteConfirm", {
          chapter: pending ? `${pending.chapter_number} — ${pending.chapter_title}` : "",
        })}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        busy={remove.isPending}
        onConfirm={() => {
          if (!pending) return;
          const id = pending.id;
          setPending(null);
          remove.mutate(id, {
            onSuccess: () => toast.success(t("taxonomyMappings.toastDeleted")),
            onError: (e) => err(e, t("taxonomyMappings.couldNotDelete")),
          });
        }}
      />
    </div>
  );
}

function MappingRow({
  mapping,
  domainLabel,
  domains,
  onDelete,
}: {
  mapping: ChapterDomainMapping;
  domainLabel: string;
  domains: { id: string; number: number; name: string }[];
  onDelete: () => void;
}) {
  const t = useT();
  const update = useUpdateMapping();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(mapping.chapter_title);
  const [domainId, setDomainId] = useState<string | null>(mapping.domain_id);

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
        <span className="font-medium text-muted-foreground">{mapping.dataset_slug}</span>
        <span>#{mapping.chapter_number}</span>
        <span className="flex-1">{mapping.chapter_title}</span>
        <span className="text-muted-foreground">{domainLabel}</span>
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          {t("taxonomyMappings.edit")}
        </Button>
        <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-md border px-3 py-2">
      <div className="min-w-[10rem] flex-1 space-y-1">
        <Label className="text-xs">{t("taxonomyMappings.chapterTitle")}</Label>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t("taxonomyMappings.domain")}</Label>
        <Select value={domainId ?? NONE} onValueChange={(v) => setDomainId(v === NONE ? null : v)}>
          <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>{t("taxonomyMappings.noDomain")}</SelectItem>
            {domains.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.number}. {d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button
        size="sm"
        disabled={update.isPending}
        onClick={() => {
          update.mutate(
            {
              id: mapping.id,
              body: {
                dataset_slug: mapping.dataset_slug,
                chapter_number: mapping.chapter_number,
                chapter_title: title.trim(),
                domain_id: domainId,
              },
            },
            {
              onSuccess: () => {
                setEditing(false);
                toast.success(t("taxonomyMappings.toastSaved"));
              },
              onError: (e) => err(e, t("taxonomyMappings.couldNotSave")),
            },
          );
        }}
      >
        {t("taxonomyMappings.save")}
      </Button>
      <Button size="sm" variant="ghost" onClick={() => {
        setTitle(mapping.chapter_title);
        setDomainId(mapping.domain_id);
        setEditing(false);
      }}>
        {t("common.cancel")}
      </Button>
    </div>
  );
}
