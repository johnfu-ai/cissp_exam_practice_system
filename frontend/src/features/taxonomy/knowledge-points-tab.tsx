"use client";

import { useState } from "react";
import {
  useKnowledgePoints, useCreateKnowledgePoint, useUpdateKnowledgePoint, useDeleteKnowledgePoint,
} from "@/lib/api/taxonomy-admin";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { Trash2 } from "lucide-react";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import type { KnowledgePoint } from "@/lib/api/types";

const NONE = "__none__";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

// Order KPs so children follow their parent, with a depth for indentation.
function ordered(kps: KnowledgePoint[]): { kp: KnowledgePoint; depth: number }[] {
  const byParent = new Map<string | null, KnowledgePoint[]>();
  kps.forEach((k) => {
    const arr = byParent.get(k.parent_id) ?? [];
    arr.push(k);
    byParent.set(k.parent_id, arr);
  });
  const out: { kp: KnowledgePoint; depth: number }[] = [];
  const visit = (parent: string | null, depth: number) => {
    (byParent.get(parent) ?? []).forEach((k) => {
      out.push({ kp: k, depth });
      visit(k.id, depth + 1);
    });
  };
  visit(null, 0);
  // Include any orphans not reachable from a null root.
  if (out.length < kps.length) {
    const seen = new Set(out.map((o) => o.kp.id));
    kps.filter((k) => !seen.has(k.id)).forEach((k) => out.push({ kp: k, depth: 0 }));
  }
  return out;
}

export function KnowledgePointsTab() {
  const kps = useKnowledgePoints();
  const create = useCreateKnowledgePoint();
  const update = useUpdateKnowledgePoint();
  const remove = useDeleteKnowledgePoint();
  const [name, setName] = useState("");
  const [parent, setParent] = useState<string | null>(null);

  if (kps.isLoading) return <Loading label="Loading knowledge points…" />;
  if (kps.isError) return <ErrorState message="Could not load knowledge points." onRetry={() => kps.refetch()} />;

  const rows = ordered(kps.data ?? []);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-6">
          <div className="flex-1 space-y-1.5">
            <Label>New knowledge point</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Risk management concepts" />
          </div>
          <div className="space-y-1.5">
            <Label>Parent</Label>
            <Select value={parent ?? NONE} onValueChange={(v) => setParent(v === NONE ? null : v)}>
              <SelectTrigger className="w-56"><SelectValue placeholder="Top level" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Top level</SelectItem>
                {kps.data?.map((k) => <SelectItem key={k.id} value={k.id}>{k.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={() => {
              if (!name.trim()) return;
              create.mutate({ name: name.trim(), parent_id: parent }, {
                onSuccess: () => { setName(""); setParent(null); toast.success("Added."); },
                onError: (e) => err(e, "Could not add knowledge point."),
              });
            }}
            disabled={create.isPending}
          >
            Add
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-1 pt-6">
          {rows.length === 0 && <p className="text-sm text-muted-foreground">No knowledge points yet.</p>}
          {rows.map(({ kp, depth }) => (
            <div key={kp.id} className="flex items-center gap-2" style={{ paddingLeft: depth * 20 }}>
              <KpRow
                kp={kp}
                onSave={(newName) => update.mutate({ id: kp.id, body: { name: newName, parent_id: kp.parent_id } }, { onError: (e) => err(e, "Could not rename.") })}
                onDelete={() => {
                  if (!window.confirm(`Delete "${kp.name}"?`)) return;
                  remove.mutate(kp.id, { onSuccess: () => toast.success("Deleted."), onError: (e) => err(e, "Could not delete (may have children/refs).") });
                }}
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function KpRow({ kp, onSave, onDelete }: { kp: KnowledgePoint; onSave: (name: string) => void; onDelete: () => void }) {
  const [name, setName] = useState(kp.name);
  return (
    <div className="flex flex-1 items-center gap-2 py-1">
      <Input className="flex-1" value={name} onChange={(e) => setName(e.target.value)} />
      <Button size="sm" variant="outline" disabled={name === kp.name} onClick={() => onSave(name)}>Save</Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
