"use client";

import { useState } from "react";
import { useTags } from "@/lib/api/taxonomy";
import { useCreateTag, useUpdateTag, useDeleteTag } from "@/lib/api/taxonomy-admin";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { Trash2 } from "lucide-react";
import type { Tag } from "@/lib/api/types";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

export function TagsTab() {
  const t = useT();
  const tags = useTags();
  const create = useCreateTag();
  const remove = useDeleteTag();
  const [name, setName] = useState("");

  if (tags.isLoading) return <Loading label={t("taxonomyTags.loading")} />;
  if (tags.isError) return <ErrorState message={t("taxonomyTags.loadFailed")} onRetry={() => tags.refetch()} />;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex items-end gap-2 p-4">
          <Input className="flex-1" placeholder={t("taxonomyTags.newTagName")} value={name} onChange={(e) => setName(e.target.value)} />
          <Button
            size="pill"
            onClick={() => {
              if (!name.trim()) return;
              create.mutate({ name: name.trim() }, {
                onSuccess: () => { setName(""); toast.success(t("taxonomyTags.toastAdded")); },
                onError: (e) => err(e, t("taxonomyTags.couldNotAddTag")),
              });
            }}
            disabled={create.isPending}
          >
            {t("taxonomyTags.addTag")}
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-1 p-4">
          {tags.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("taxonomyTags.noTags")}</p>}
          {tags.data?.map((tg) => (
            <TagRow
              key={tg.id}
              tag={tg}
              onDelete={() => {
                if (!window.confirm(t("taxonomyTags.deleteTagConfirm", { name: tg.name }))) return;
                remove.mutate(tg.id, { onSuccess: () => toast.success(t("taxonomyTags.toastDeleted")), onError: (e) => err(e, t("taxonomyTags.couldNotDeleteTag")) });
              }}
            />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function TagRow({ tag, onDelete }: { tag: Tag; onDelete: () => void }) {
  const t = useT();
  const [name, setName] = useState(tag.name);
  const update = useUpdateTag();
  return (
    <div className="flex items-center gap-2 py-1">
      <Input className="flex-1" value={name} onChange={(e) => setName(e.target.value)} />
      <Button size="sm" variant="outline" disabled={name === tag.name || update.isPending}
        onClick={() => update.mutate({ id: tag.id, body: { name } }, { onSuccess: () => toast.success(t("taxonomyTags.toastSaved")), onError: (e) => err(e, t("taxonomyTags.couldNotSaveTag")) })}>
        {t("taxonomyTags.save")}
      </Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
