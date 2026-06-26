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
import { Trash2 } from "lucide-react";
import type { Tag } from "@/lib/api/types";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

export function TagsTab() {
  const tags = useTags();
  const create = useCreateTag();
  const remove = useDeleteTag();
  const [name, setName] = useState("");

  if (tags.isLoading) return <Loading label="Loading tags…" />;
  if (tags.isError) return <ErrorState message="Could not load tags." onRetry={() => tags.refetch()} />;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex items-end gap-2 p-4">
          <Input className="flex-1" placeholder="New tag name" value={name} onChange={(e) => setName(e.target.value)} />
          <Button
            size="pill"
            onClick={() => {
              if (!name.trim()) return;
              create.mutate({ name: name.trim() }, {
                onSuccess: () => { setName(""); toast.success("Tag added."); },
                onError: (e) => err(e, "Could not add tag."),
              });
            }}
            disabled={create.isPending}
          >
            Add tag
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-1 p-4">
          {tags.data?.length === 0 && <p className="text-sm text-muted-foreground">No tags yet.</p>}
          {tags.data?.map((t) => (
            <TagRow
              key={t.id}
              tag={t}
              onDelete={() => {
                if (!window.confirm(`Delete tag "${t.name}"?`)) return;
                remove.mutate(t.id, { onSuccess: () => toast.success("Deleted."), onError: (e) => err(e, "Could not delete tag.") });
              }}
            />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function TagRow({ tag, onDelete }: { tag: Tag; onDelete: () => void }) {
  const [name, setName] = useState(tag.name);
  const update = useUpdateTag();
  return (
    <div className="flex items-center gap-2 py-1">
      <Input className="flex-1" value={name} onChange={(e) => setName(e.target.value)} />
      <Button size="sm" variant="outline" disabled={name === tag.name || update.isPending}
        onClick={() => update.mutate({ id: tag.id, body: { name } }, { onSuccess: () => toast.success("Saved."), onError: (e) => err(e, "Could not save tag.") })}>
        Save
      </Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
