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
import { useT } from "@/lib/i18n/provider";
import { Trash2 } from "lucide-react";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import type { KnowledgePoint } from "@/lib/api/types";

const NONE = "__none__";

// Tailwind classes for KP-tree indentation (one per depth level; 20px steps
// matching the previous inline style). Literal strings so the JIT picks them up.
const DEPTH_PL = [
  "pl-0",
  "pl-[20px]",
  "pl-[40px]",
  "pl-[60px]",
  "pl-[80px]",
  "pl-[100px]",
  "pl-[120px]",
  "pl-[140px]",
  "pl-[160px]",
  "pl-[180px]",
];

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
  const t = useT();
  const kps = useKnowledgePoints();
  const create = useCreateKnowledgePoint();
  const update = useUpdateKnowledgePoint();
  const remove = useDeleteKnowledgePoint();
  const [name, setName] = useState("");
  const [parent, setParent] = useState<string | null>(null);

  if (kps.isLoading) return <Loading label={t("taxonomyKps.loading")} />;
  if (kps.isError) return <ErrorState message={t("taxonomyKps.loadFailed")} onRetry={() => kps.refetch()} />;

  const rows = ordered(kps.data ?? []);

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="flex-1 space-y-1.5">
            <Label>{t("taxonomyKps.newKp")}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("taxonomyKps.newKpPlaceholder")} />
          </div>
          <div className="space-y-1.5">
            <Label>{t("taxonomyKps.parent")}</Label>
            <Select value={parent ?? NONE} onValueChange={(v) => setParent(v === NONE ? null : v)}>
              <SelectTrigger className="w-56"><SelectValue placeholder={t("taxonomyKps.topLevel")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>{t("taxonomyKps.topLevel")}</SelectItem>
                {kps.data?.map((k) => <SelectItem key={k.id} value={k.id}>{k.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button
            size="pill"
            onClick={() => {
              if (!name.trim()) return;
              create.mutate({ name: name.trim(), parent_id: parent }, {
                onSuccess: () => { setName(""); setParent(null); toast.success(t("taxonomyKps.toastAdded")); },
                onError: (e) => err(e, t("taxonomyKps.couldNotAdd")),
              });
            }}
            disabled={create.isPending}
          >
            {t("taxonomyKps.add")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-1 p-4">
          {rows.length === 0 && <p className="text-sm text-muted-foreground">{t("taxonomyKps.noKps")}</p>}
          {rows.map(({ kp, depth }) => (
            <div key={kp.id} className={`flex items-center gap-2 ${DEPTH_PL[depth] ?? DEPTH_PL[DEPTH_PL.length - 1]}`}>
              <KpRow
                kp={kp}
                onSave={(newName) => update.mutate({ id: kp.id, body: { name: newName, parent_id: kp.parent_id } }, { onError: (e) => err(e, t("taxonomyKps.couldNotRename")) })}
                onDelete={() => {
                  if (!window.confirm(t("taxonomyKps.deleteConfirm", { name: kp.name }))) return;
                  remove.mutate(kp.id, { onSuccess: () => toast.success(t("taxonomyKps.toastDeleted")), onError: (e) => err(e, t("taxonomyKps.couldNotDelete")) });
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
  const t = useT();
  const [name, setName] = useState(kp.name);
  return (
    <div className="flex flex-1 items-center gap-2 py-1">
      <Input className="flex-1" value={name} onChange={(e) => setName(e.target.value)} />
      <Button size="sm" variant="outline" disabled={name === kp.name} onClick={() => onSave(name)}>{t("taxonomyKps.save")}</Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
