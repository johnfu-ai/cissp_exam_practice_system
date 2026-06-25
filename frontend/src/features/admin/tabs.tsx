"use client";

import { useState } from "react";
import {
  useAdminUsers, useSetUserStatus, useSetUserRoles,
  useClasses, useCreateClass, useDeleteClass, useClassMembers,
  useCatParams, useCreateCatParams, useSetCurrentCatParams,
  useQualityDashboard, useQualityFeedback, useResolveFeedback, useLowAccuracy,
  useAuditLogs, useReportSummary,
} from "@/lib/api/admin";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { fmtDate, fmtPct } from "@/features/analytics/format";
import type { AdminClass, RoleName } from "@/lib/api/types";

const ROLES: RoleName[] = ["individual_learner", "instructor", "content_editor", "org_admin", "system_admin"];
const AUDIT_ACTIONS = ["login", "logout", "import", "edit", "publish", "delete", "archive", "permission_change", "config_change"];
const ANY = "__any__";

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

/* ---------------- Users ---------------- */
export function UsersTab() {
  const [search, setSearch] = useState("");
  const [input, setInput] = useState("");
  const users = useAdminUsers(search);
  const setStatus = useSetUserStatus();
  const setRoles = useSetUserRoles();

  if (users.isLoading) return <Loading label="Loading users…" />;
  if (users.isError) return <ErrorState message="Could not load users." onRetry={() => users.refetch()} />;

  return (
    <div className="space-y-4">
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setSearch(input.trim()); }}>
        <Input className="w-64" placeholder="Search email / name…" value={input} onChange={(e) => setInput(e.target.value)} />
        <Button type="submit" variant="outline">Search</Button>
      </form>
      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Roles</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data?.items.map((u) => (
                <tr key={u.id} className="border-b last:border-0 align-top">
                  <td className="px-4 py-2">
                    <div>{u.email}</div>
                    {u.display_name && <div className="text-xs text-muted-foreground">{u.display_name}</div>}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.map((r) => <Badge key={r} variant="outline">{labelize(r)}</Badge>)}
                    </div>
                    <RolePicker
                      current={u.roles}
                      onAdd={(role) => setRoles.mutate({ id: u.id, roleNames: [...new Set([...u.roles, role])] as RoleName[] }, { onError: (e) => err(e, "Could not update roles.") })}
                    />
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={u.status === "active" ? "success" : "destructive"}>{u.status}</Badge>
                  </td>
                  <td className="px-4 py-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={setStatus.isPending}
                      onClick={() => setStatus.mutate({ id: u.id, status: u.status === "active" ? "disabled" : "active" }, { onError: (e) => err(e, "Could not change status.") })}
                    >
                      {u.status === "active" ? "Disable" : "Enable"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">{users.data?.total ?? 0} users</p>
    </div>
  );
}

function RolePicker({ current, onAdd }: { current: string[]; onAdd: (r: RoleName) => void }) {
  const addable = ROLES.filter((r) => !current.includes(r));
  if (addable.length === 0) return null;
  return (
    <Select value={ANY} onValueChange={(v) => v !== ANY && onAdd(v as RoleName)}>
      <SelectTrigger className="mt-1 h-7 w-40 text-xs"><SelectValue placeholder="+ Add role" /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ANY}>+ Add role</SelectItem>
        {addable.map((r) => <SelectItem key={r} value={r}>{labelize(r)}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

/* ---------------- Classes ---------------- */
export function ClassesTab() {
  const classes = useClasses();
  const create = useCreateClass();
  const remove = useDeleteClass();
  const [name, setName] = useState("");

  if (classes.isLoading) return <Loading label="Loading classes…" />;
  if (classes.isError) return <ErrorState message="Could not load classes." onRetry={() => classes.refetch()} />;

  const items: AdminClass[] = Array.isArray(classes.data) ? classes.data : classes.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-2 rounded-md border border-dashed p-3">
        <Input className="flex-1" placeholder="New class name" value={name} onChange={(e) => setName(e.target.value)} />
        <Button onClick={() => {
          if (!name.trim()) return;
          create.mutate({ name: name.trim() }, { onSuccess: () => { setName(""); toast.success("Class created."); }, onError: (e) => err(e, "Could not create class.") });
        }} disabled={create.isPending}>Add class</Button>
      </div>
      {items.length === 0 && <p className="text-sm text-muted-foreground">No classes yet.</p>}
      {items.map((c) => <ClassCard key={c.id} cls={c} onDelete={() => {
        if (!window.confirm(`Delete class "${c.name}"?`)) return;
        remove.mutate(c.id, { onSuccess: () => toast.success("Deleted."), onError: (e) => err(e, "Could not delete class.") });
      }} />)}
    </div>
  );
}

function ClassCard({ cls, onDelete }: { cls: AdminClass; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const members = useClassMembers(cls.id, open);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base">{cls.name}</CardTitle>
          <p className="text-xs text-muted-foreground">{cls.member_count} members</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Members"}</Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}>Delete</Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="space-y-1">
          {members.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {members.data?.length === 0 && <p className="text-sm text-muted-foreground">No members.</p>}
          {members.data?.map((m) => (
            <div key={m.user_id} className="text-sm">{m.email}{m.display_name ? ` · ${m.display_name}` : ""}</div>
          ))}
        </CardContent>
      )}
    </Card>
  );
}

/* ---------------- CAT params ---------------- */
export function CatParamsTab() {
  const versions = useCatParams();
  const create = useCreateCatParams();
  const setCurrent = useSetCurrentCatParams();
  const [form, setForm] = useState({ version_label: "", effective_date: new Date().toISOString().slice(0, 10), k0: 1, decay: 0.05, base_se: 1, early_stop_enabled: true });

  if (versions.isLoading) return <Loading label="Loading CAT parameters…" />;
  if (versions.isError) return <ErrorState message="Could not load CAT parameters." onRetry={() => versions.refetch()} />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>New CAT parameter version</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="space-y-1.5"><Label>Version label</Label><Input value={form.version_label} onChange={(e) => setForm((f) => ({ ...f, version_label: e.target.value }))} /></div>
          <div className="space-y-1.5"><Label>Effective date</Label><Input type="date" value={form.effective_date} onChange={(e) => setForm((f) => ({ ...f, effective_date: e.target.value }))} /></div>
          <div className="space-y-1.5"><Label>k0</Label><Input type="number" step="0.1" value={form.k0} onChange={(e) => setForm((f) => ({ ...f, k0: Number(e.target.value) }))} /></div>
          <div className="space-y-1.5"><Label>decay</Label><Input type="number" step="0.01" value={form.decay} onChange={(e) => setForm((f) => ({ ...f, decay: Number(e.target.value) }))} /></div>
          <div className="space-y-1.5"><Label>base_se</Label><Input type="number" step="0.1" value={form.base_se} onChange={(e) => setForm((f) => ({ ...f, base_se: Number(e.target.value) }))} /></div>
          <div className="flex items-end">
            <Button onClick={() => {
              if (!form.version_label.trim()) { toast.error("Version label is required."); return; }
              create.mutate(
                { version_label: form.version_label.trim(), effective_date: form.effective_date, params: { k0: form.k0, decay: form.decay, base_se: form.base_se, early_stop_enabled: form.early_stop_enabled }, set_current: true },
                { onSuccess: () => { toast.success("Version created."); setForm((f) => ({ ...f, version_label: "" })); }, onError: (e) => err(e, "Could not create version.") }
              );
            }} disabled={create.isPending}>Create &amp; set current</Button>
          </div>
        </CardContent>
      </Card>
      {versions.data?.map((v) => (
        <Card key={v.id}>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">{v.version_label}{v.is_current && <Badge variant="success">Current</Badge>}</CardTitle>
              <p className="text-xs text-muted-foreground">{v.effective_date} · {Object.entries(v.params).map(([k, val]) => `${k}=${val}`).join(", ")}</p>
            </div>
            {!v.is_current && <Button variant="outline" size="sm" onClick={() => setCurrent.mutate(v.id, { onSuccess: () => toast.success("Set current."), onError: (e) => err(e, "Could not set current.") })}>Set current</Button>}
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

/* ---------------- Quality ---------------- */
export function QualityTab() {
  const dash = useQualityDashboard();
  const feedback = useQualityFeedback();
  const lowAcc = useLowAccuracy();
  const resolve = useResolveFeedback();

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Open feedback" value={dash.data?.open_feedback_count ?? 0} />
        <Stat label="Low accuracy" value={dash.data?.low_accuracy_question_count ?? 0} />
        <Stat label="Missing explanation" value={dash.data?.missing_explanation_count ?? 0} />
        <Stat label="Disputed" value={dash.data?.disputed_question_count ?? 0} />
      </div>

      <Card>
        <CardHeader><CardTitle>Open feedback</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {feedback.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {feedback.data?.items.length === 0 && <p className="text-sm text-muted-foreground">No open feedback.</p>}
          {feedback.data?.items.map((f) => (
            <div key={f.id} className="flex items-start justify-between gap-3 rounded-md border p-2 text-sm">
              <div>
                <Badge variant="outline">{labelize(f.feedback_type)}</Badge>
                {f.comment && <p className="mt-1 text-muted-foreground">{f.comment}</p>}
              </div>
              <div className="flex shrink-0 gap-2">
                <Button size="sm" variant="outline" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: f.id, status: "resolved" }, { onSuccess: () => toast.success("Resolved."), onError: (e) => err(e, "Could not resolve.") })}>Resolve</Button>
                <Button size="sm" variant="ghost" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: f.id, status: "wont_fix" }, { onSuccess: () => toast.message("Marked won't fix."), onError: (e) => err(e, "Could not update.") })}>Won&apos;t fix</Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Low-accuracy questions</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {lowAcc.data?.length === 0 && <p className="text-sm text-muted-foreground">None flagged.</p>}
          {lowAcc.data?.map((q) => (
            <div key={q.question_id} className="flex items-center justify-between gap-3 text-sm">
              <span className="max-w-md truncate">{q.stem}</span>
              <span className="text-muted-foreground">{fmtPct(q.accuracy)} ({q.correct}/{q.answered})</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

/* ---------------- Audit ---------------- */
export function AuditTab() {
  const [action, setAction] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const logs = useAuditLogs(action, offset);

  return (
    <div className="space-y-4">
      <Select value={action ?? ANY} onValueChange={(v) => { setOffset(0); setAction(v === ANY ? null : v); }}>
        <SelectTrigger className="w-52"><SelectValue placeholder="All actions" /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>All actions</SelectItem>
          {AUDIT_ACTIONS.map((a) => <SelectItem key={a} value={a}>{labelize(a)}</SelectItem>)}
        </SelectContent>
      </Select>
      {logs.isLoading && <Loading label="Loading audit log…" />}
      {logs.isError && <ErrorState message="Could not load audit logs." onRetry={() => logs.refetch()} />}
      {logs.data && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="px-4 py-2 font-medium">When</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Entity</th>
                  <th className="px-4 py-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.data.items.map((l) => (
                  <tr key={l.id} className="border-b last:border-0 align-top">
                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{fmtDate(l.occurred_at)}</td>
                    <td className="px-4 py-2"><Badge variant="outline">{labelize(l.action)}</Badge></td>
                    <td className="px-4 py-2 text-muted-foreground">{l.entity_type ?? "—"}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {l.details ? JSON.stringify(l.details).slice(0, 80) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
      {logs.data && logs.data.total > logs.data.limit && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{logs.data.total} entries</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - logs.data!.limit))}>Previous</Button>
            <Button variant="outline" size="sm" disabled={offset + logs.data.limit >= logs.data.total} onClick={() => setOffset((o) => o + logs.data!.limit)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Reports ---------------- */
export function ReportsTab() {
  const [window, setWindow] = useState<30 | 90>(30);
  const report = useReportSummary(window);

  if (report.isLoading) return <Loading label="Loading report…" />;
  if (report.isError) return <ErrorState message="Could not load the report." onRetry={() => report.refetch()} />;
  const r = report.data!;

  return (
    <div className="space-y-4">
      <div className="flex gap-1">
        {([30, 90] as const).map((w) => (
          <Button key={w} variant={window === w ? "default" : "outline"} size="sm" onClick={() => setWindow(w)}>{w}d</Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Active users" value={r.active_users} />
        <Stat label="Practice sessions" value={r.practice_session_count} />
        <Stat label="Exam sessions" value={r.exam_session_count} />
        <Stat label="Overall accuracy" value={fmtPct(r.accuracy)} />
        <Stat label="Total answers" value={r.total_answers} />
        <Stat label="Published questions" value={r.published_question_count} />
        <Stat label="Used questions" value={r.used_question_count} />
        <Stat label="Bank usage" value={fmtPct(r.question_bank_usage_pct / 100)} />
      </div>
      <Card>
        <CardHeader><CardTitle>Top error questions</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {r.top_error_questions.length === 0 && <p className="text-sm text-muted-foreground">None.</p>}
          {r.top_error_questions.map((q) => (
            <div key={q.question_id} className="flex items-center justify-between gap-3 text-sm">
              <span className="max-w-md truncate">{q.stem}</span>
              <span className="text-muted-foreground">{fmtPct(q.accuracy)} ({q.correct}/{q.answered})</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
