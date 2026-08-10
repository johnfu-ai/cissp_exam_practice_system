"use client";

import { useState } from "react";
import {
  useKnowledgePoints, useCreateKnowledgePoint, useUpdateKnowledgePoint, useDeleteKnowledgePoint,
  useKpDomains, useBindKpDomain, useUnbindKpDomain,
} from "@/lib/api/taxonomy-admin";
import { useDomains } from "@/lib/api/taxonomy";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { ChevronDown, ChevronRight, Trash2 } from "lucide-react";
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
  const [pendingKp, setPendingKp] = useState<KnowledgePoint | null>(null);

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
            <div key={kp.id} className={DEPTH_PL[depth] ?? DEPTH_PL[DEPTH_PL.length - 1]}>
              <KpRow
                kp={kp}
                onSave={(newName) => update.mutate({ id: kp.id, body: { name: newName, parent_id: kp.parent_id } }, { onError: (e) => err(e, t("taxonomyKps.couldNotRename")) })}
                onDelete={() => setPendingKp(kp)}
              />
            </div>
          ))}
        </CardContent>
      </Card>
      <ConfirmDialog
        open={!!pendingKp}
        onOpenChange={(o) => !o && setPendingKp(null)}
        title={t("taxonomyKps.deleteConfirm", { name: pendingKp?.name ?? "" })}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        busy={remove.isPending}
        onConfirm={() => {
          if (!pendingKp) return;
          const id = pendingKp.id;
          setPendingKp(null);
          remove.mutate(id, { onSuccess: () => toast.success(t("taxonomyKps.toastDeleted")), onError: (e) => err(e, t("taxonomyKps.couldNotDelete")) });
        }}
      />
    </div>
  );
}

function KpRow({ kp, onSave, onDelete }: { kp: KnowledgePoint; onSave: (name: string) => void; onDelete: () => void }) {
  const t = useT();
  const [name, setName] = useState(kp.name);
  const [domainsOpen, setDomainsOpen] = useState(false);
  return (
    <div className="space-y-1 py-1">
      <div className="flex flex-1 items-center gap-2">
        <Input className="flex-1" value={name} onChange={(e) => setName(e.target.value)} />
        <Button size="sm" variant="outline" disabled={name === kp.name} onClick={() => onSave(name)}>{t("taxonomyKps.save")}</Button>
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={domainsOpen}
          onClick={() => setDomainsOpen((o) => !o)}
        >
          {domainsOpen ? <ChevronDown className="mr-1 h-4 w-4" /> : <ChevronRight className="mr-1 h-4 w-4" />}
          {t("taxonomyKps.domains")}
        </Button>
        <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
      </div>
      {domainsOpen && <KpDomainBindings kpId={kp.id} />}
    </div>
  );
}

export function KpDomainBindings({ kpId }: { kpId: string }) {
  const t = useT();
  const allDomains = useDomains();
  const bound = useKpDomains(kpId);
  const bind = useBindKpDomain();
  const unbind = useUnbindKpDomain();

  if (allDomains.isLoading || bound.isLoading) {
    return <p className="pl-2 text-xs text-muted-foreground">{t("taxonomyKps.domainsLoading")}</p>;
  }
  if (allDomains.isError || bound.isError) {
    return <p className="pl-2 text-xs text-destructive">{t("taxonomyKps.domainsLoadFailed")}</p>;
  }

  const boundIds = new Set((bound.data ?? []).map((d) => d.id));
  const busy = bind.isPending || unbind.isPending;

  return (
    <div
      className="ml-2 grid gap-2 rounded-md border bg-muted/30 p-3 sm:grid-cols-2"
      data-testid={`kp-domains-${kpId}`}
    >
      <p className="sm:col-span-2 text-xs text-muted-foreground">{t("taxonomyKps.domainsHint")}</p>
      {(allDomains.data ?? []).map((d) => {
        const checked = boundIds.has(d.id);
        const id = `kp-${kpId}-domain-${d.id}`;
        return (
          <label key={d.id} htmlFor={id} className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox
              id={id}
              checked={checked}
              disabled={busy}
              onCheckedChange={(next) => {
                if (next === checked) return;
                if (next) {
                  bind.mutate(
                    { kpId, domainId: d.id },
                    { onError: (e) => err(e, t("taxonomyKps.couldNotBind")) },
                  );
                } else {
                  unbind.mutate(
                    { kpId, domainId: d.id },
                    { onError: (e) => err(e, t("taxonomyKps.couldNotUnbind")) },
                  );
                }
              }}
            />
            <span>{d.number}. {d.name}</span>
          </label>
        );
      })}
      {(allDomains.data ?? []).length === 0 && (
        <p className="sm:col-span-2 text-xs text-muted-foreground">{t("taxonomyKps.noDomains")}</p>
      )}
    </div>
  );
}
