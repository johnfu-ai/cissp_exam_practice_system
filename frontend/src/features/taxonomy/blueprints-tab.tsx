"use client";

import { useState } from "react";
import {
  useBlueprints,
  useCreateBlueprint,
  useSetCurrentBlueprint,
  useDeleteBlueprint,
  useCreateDomain,
  useUpdateDomain,
  useDeleteDomain,
} from "@/lib/api/taxonomy-admin";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { Trash2 } from "lucide-react";
import type { Blueprint, BlueprintInput, Domain } from "@/lib/api/types";

const EMPTY: BlueprintInput = {
  version_label: "",
  effective_date: new Date().toISOString().slice(0, 10),
  min_items: 100,
  max_items: 150,
  duration_minutes: 180,
  passing_score: 700,
  max_score: 1000,
};

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

export function BlueprintsTab() {
  const blueprints = useBlueprints();
  const create = useCreateBlueprint();
  const setCurrent = useSetCurrentBlueprint();
  const remove = useDeleteBlueprint();
  const [form, setForm] = useState<BlueprintInput>(EMPTY);
  const [showForm, setShowForm] = useState(false);

  if (blueprints.isLoading) return <Loading label="Loading blueprints…" />;
  if (blueprints.isError) return <ErrorState message="Could not load blueprints." onRetry={() => blueprints.refetch()} />;

  function num<K extends keyof BlueprintInput>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: Number(v) }));
  }

  function submit() {
    if (!form.version_label.trim()) {
      toast.error("Version label is required.");
      return;
    }
    create.mutate(form, {
      onSuccess: () => {
        toast.success("Blueprint created.");
        setForm(EMPTY);
        setShowForm(false);
      },
      onError: (e) => err(e, "Could not create the blueprint."),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant={showForm ? "outline" : "default"} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "Cancel" : "New blueprint"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader><CardTitle>New exam blueprint</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="col-span-2 space-y-1.5">
              <Label>Version label</Label>
              <Input value={form.version_label} onChange={(e) => setForm((f) => ({ ...f, version_label: e.target.value }))} placeholder="2024-04-15" />
            </div>
            <div className="space-y-1.5">
              <Label>Effective date</Label>
              <Input type="date" value={form.effective_date} onChange={(e) => setForm((f) => ({ ...f, effective_date: e.target.value }))} />
            </div>
            <div className="space-y-1.5"><Label>Min items</Label><Input type="number" value={form.min_items} onChange={(e) => num("min_items", e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Max items</Label><Input type="number" value={form.max_items} onChange={(e) => num("max_items", e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Duration (min)</Label><Input type="number" value={form.duration_minutes} onChange={(e) => num("duration_minutes", e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Passing score</Label><Input type="number" value={form.passing_score} onChange={(e) => num("passing_score", e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Max score</Label><Input type="number" value={form.max_score} onChange={(e) => num("max_score", e.target.value)} /></div>
            <div className="col-span-2 flex items-end sm:col-span-4">
              <Button onClick={submit} disabled={create.isPending}>{create.isPending ? "Creating…" : "Create blueprint"}</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {blueprints.data?.map((bp) => (
        <BlueprintCard
          key={bp.id}
          bp={bp}
          onSetCurrent={() =>
            setCurrent.mutate(bp.id, {
              onSuccess: () => toast.success("Set as current."),
              onError: (e) => err(e, "Could not set current."),
            })
          }
          onDelete={() => {
            if (!window.confirm(`Delete blueprint ${bp.version_label}?`)) return;
            remove.mutate(bp.id, {
              onSuccess: () => toast.success("Deleted."),
              onError: (e) => err(e, "Could not delete (may be referenced)."),
            });
          }}
        />
      ))}
    </div>
  );
}

function BlueprintCard({ bp, onSetCurrent, onDelete }: { bp: Blueprint; onSetCurrent: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const totalWeight = bp.domains.reduce((s, d) => s + d.weight_pct, 0);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            {bp.version_label}
            {bp.is_current && <Badge variant="success">Current</Badge>}
          </CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            {bp.effective_date} · {bp.min_items}–{bp.max_items} items · {bp.duration_minutes}m · pass {bp.passing_score}/{bp.max_score}
          </p>
        </div>
        <div className="flex gap-2">
          {!bp.is_current && <Button variant="outline" size="sm" onClick={onSetCurrent}>Set current</Button>}
          <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Domains"}</Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent>
          <DomainEditor blueprintId={bp.id} domains={bp.domains} />
          <p className={`mt-2 text-xs ${totalWeight === 100 ? "text-muted-foreground" : "text-amber-600"}`}>
            Total weight: {totalWeight}% {totalWeight !== 100 && "(should sum to 100%)"}
          </p>
        </CardContent>
      )}
    </Card>
  );
}

function DomainEditor({ blueprintId, domains }: { blueprintId: string; domains: Domain[] }) {
  const create = useCreateDomain();
  const update = useUpdateDomain();
  const remove = useDeleteDomain();
  const [n, setN] = useState("");
  const [name, setName] = useState("");
  const [w, setW] = useState("");

  function add() {
    if (!name.trim()) return;
    create.mutate(
      { blueprintId, body: { number: Number(n) || 0, name: name.trim(), weight_pct: Number(w) || 0 } },
      {
        onSuccess: () => { setN(""); setName(""); setW(""); },
        onError: (e) => err(e, "Could not add domain."),
      }
    );
  }

  return (
    <div className="space-y-2">
      {domains.map((d) => (
        <DomainRow
          key={d.id}
          d={d}
          onSave={(body) => update.mutate({ blueprintId, domainId: d.id, body }, { onError: (e) => err(e, "Could not update domain.") })}
          onDelete={() => {
            if (!window.confirm(`Delete domain ${d.name}?`)) return;
            remove.mutate({ blueprintId, domainId: d.id }, { onError: (e) => err(e, "Could not delete domain.") });
          }}
        />
      ))}
      <div className="flex items-end gap-2 rounded-md border border-dashed p-2">
        <Input className="w-16" placeholder="#" value={n} onChange={(e) => setN(e.target.value)} />
        <Input className="flex-1" placeholder="Domain name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input className="w-20" placeholder="wt%" value={w} onChange={(e) => setW(e.target.value)} />
        <Button size="sm" onClick={add} disabled={create.isPending}>Add</Button>
      </div>
    </div>
  );
}

function DomainRow({ d, onSave, onDelete }: { d: Domain; onSave: (b: { number: number; name: string; weight_pct: number }) => void; onDelete: () => void }) {
  const [number, setNumber] = useState(String(d.number));
  const [name, setName] = useState(d.name);
  const [weight, setWeight] = useState(String(d.weight_pct));
  const dirty = number !== String(d.number) || name !== d.name || weight !== String(d.weight_pct);
  return (
    <div className="flex items-center gap-2">
      <Input className="w-16" value={number} onChange={(e) => setNumber(e.target.value)} />
      <Input className="flex-1" value={name} onChange={(e) => setName(e.target.value)} />
      <Input className="w-20" value={weight} onChange={(e) => setWeight(e.target.value)} />
      <Button size="sm" variant="outline" disabled={!dirty} onClick={() => onSave({ number: Number(number), name, weight_pct: Number(weight) })}>Save</Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
