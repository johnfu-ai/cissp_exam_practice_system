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
import { useT } from "@/lib/i18n/provider";
import { enumLabel } from "@/features/shared/enum-label";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { fmtDate, fmtPct } from "@/features/analytics/format";
import type { AdminClass, RoleName } from "@/lib/api/types";

const ROLES: RoleName[] = ["individual_learner", "instructor", "content_editor", "org_admin", "system_admin"];
const AUDIT_ACTIONS = ["login", "logout", "import", "edit", "publish", "delete", "archive", "permission_change", "config_change"];
const ANY = "__any__";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

/* ---------------- Users ---------------- */
export function UsersTab() {
  const t = useT();
  const [search, setSearch] = useState("");
  const [input, setInput] = useState("");
  const users = useAdminUsers(search);
  const setStatus = useSetUserStatus();
  const setRoles = useSetUserRoles();

  if (users.isLoading) return <Loading label={t("adminTab.loadingUsers")} />;
  if (users.isError) return <ErrorState message={t("adminTab.loadFailedUsers")} onRetry={() => users.refetch()} />;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-4">
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setSearch(input.trim()); }}>
            <Input className="w-64" placeholder={t("adminTab.searchEmailPlaceholder")} value={input} onChange={(e) => setInput(e.target.value)} />
            <Button type="submit" variant="outline" size="sm">{t("adminTab.search")}</Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-4 py-2 font-medium">{t("adminTab.colEmail")}</th>
                <th className="px-4 py-2 font-medium">{t("adminTab.colRoles")}</th>
                <th className="px-4 py-2 font-medium">{t("adminTab.colStatus")}</th>
                <th className="px-4 py-2 font-medium">{t("adminTab.colActions")}</th>
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
                      {u.roles.map((r) => <Badge key={r} variant="outline">{enumLabel(t, "role", r)}</Badge>)}
                    </div>
                    <RolePicker
                      current={u.roles}
                      onAdd={(role) => setRoles.mutate({ id: u.id, roleNames: [...new Set([...u.roles, role])] as RoleName[] }, { onError: (e) => err(e, t("adminTab.couldNotUpdateRoles")) })}
                    />
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={u.status === "active" ? "success" : "destructive"}>{enumLabel(t, "userStatus", u.status)}</Badge>
                  </td>
                  <td className="px-4 py-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={setStatus.isPending}
                      onClick={() => setStatus.mutate({ id: u.id, status: u.status === "active" ? "disabled" : "active" }, { onError: (e) => err(e, t("adminTab.couldNotChangeStatus")) })}
                    >
                      {u.status === "active" ? t("adminTab.disable") : t("adminTab.enable")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">{t("adminTab.nUsers", { n: users.data?.total ?? 0 })}</p>
    </div>
  );
}

function RolePicker({ current, onAdd }: { current: string[]; onAdd: (r: RoleName) => void }) {
  const t = useT();
  const addable = ROLES.filter((r) => !current.includes(r));
  if (addable.length === 0) return null;
  return (
    <Select value={ANY} onValueChange={(v) => v !== ANY && onAdd(v as RoleName)}>
      <SelectTrigger className="mt-1 h-7 w-40 text-xs"><SelectValue placeholder={t("adminTab.addRole")} /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ANY}>{t("adminTab.addRole")}</SelectItem>
        {addable.map((r) => <SelectItem key={r} value={r}>{enumLabel(t, "role", r)}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

/* ---------------- Classes ---------------- */
export function ClassesTab() {
  const t = useT();
  const classes = useClasses();
  const create = useCreateClass();
  const remove = useDeleteClass();
  const [name, setName] = useState("");

  if (classes.isLoading) return <Loading label={t("adminTab.loadingClasses")} />;
  if (classes.isError) return <ErrorState message={t("adminTab.loadFailedClasses")} onRetry={() => classes.refetch()} />;

  const items: AdminClass[] = Array.isArray(classes.data) ? classes.data : classes.data?.items ?? [];

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex items-end gap-2 p-4">
          <Input className="flex-1" placeholder={t("adminTab.newClassName")} value={name} onChange={(e) => setName(e.target.value)} />
          <Button size="pill" onClick={() => {
            if (!name.trim()) return;
            create.mutate({ name: name.trim() }, { onSuccess: () => { setName(""); toast.success(t("adminTab.toastClassCreated")); }, onError: (e) => err(e, t("adminTab.couldNotCreateClass")) });
          }} disabled={create.isPending}>{t("adminTab.addClass")}</Button>
        </CardContent>
      </Card>
      {items.length === 0 && <p className="text-sm text-muted-foreground">{t("adminTab.noClasses")}</p>}
      {items.map((c) => <ClassCard key={c.id} cls={c} onDelete={() => {
        if (!window.confirm(t("adminTab.deleteClassConfirm", { name: c.name }))) return;
        remove.mutate(c.id, { onSuccess: () => toast.success(t("adminTab.toastDeleted")), onError: (e) => err(e, t("adminTab.couldNotDeleteClass")) });
      }} />)}
    </div>
  );
}

function ClassCard({ cls, onDelete }: { cls: AdminClass; onDelete: () => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const members = useClassMembers(cls.id, open);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base">{cls.name}</CardTitle>
          <p className="text-xs text-muted-foreground">{t("adminTab.nMembers", { n: cls.member_count })}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>{open ? t("adminTab.hide") : t("adminTab.members")}</Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}>{t("adminTab.delete")}</Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="space-y-1">
          {members.isLoading && <p className="text-sm text-muted-foreground">{t("adminTab.loading")}</p>}
          {members.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("adminTab.noMembers")}</p>}
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
  const t = useT();
  const versions = useCatParams();
  const create = useCreateCatParams();
  const setCurrent = useSetCurrentCatParams();
  const [form, setForm] = useState({ version_label: "", effective_date: new Date().toISOString().slice(0, 10), k0: 1, decay: 0.05, base_se: 1, early_stop_enabled: true });

  if (versions.isLoading) return <Loading label={t("adminTab.loadingCat")} />;
  if (versions.isError) return <ErrorState message={t("adminTab.loadFailedCat")} onRetry={() => versions.refetch()} />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>{t("adminTab.newVersionTitle")}</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="space-y-1.5"><Label>{t("adminTab.versionLabel")}</Label><Input value={form.version_label} onChange={(e) => setForm((f) => ({ ...f, version_label: e.target.value }))} /></div>
          <div className="space-y-1.5"><Label>{t("adminTab.effectiveDate")}</Label><Input type="date" value={form.effective_date} onChange={(e) => setForm((f) => ({ ...f, effective_date: e.target.value }))} /></div>
          <div className="space-y-1.5"><Label>k0</Label><Input type="number" step="0.1" value={form.k0} onChange={(e) => setForm((f) => ({ ...f, k0: Number(e.target.value) }))} /></div>
          <div className="space-y-1.5"><Label>decay</Label><Input type="number" step="0.01" value={form.decay} onChange={(e) => setForm((f) => ({ ...f, decay: Number(e.target.value) }))} /></div>
          <div className="space-y-1.5"><Label>base_se</Label><Input type="number" step="0.1" value={form.base_se} onChange={(e) => setForm((f) => ({ ...f, base_se: Number(e.target.value) }))} /></div>
          <div className="flex items-end">
            <Button size="pill" onClick={() => {
              if (!form.version_label.trim()) { toast.error(t("adminTab.toastVersionLabelRequired")); return; }
              create.mutate(
                { version_label: form.version_label.trim(), effective_date: form.effective_date, params: { k0: form.k0, decay: form.decay, base_se: form.base_se, early_stop_enabled: form.early_stop_enabled }, set_current: true },
                { onSuccess: () => { toast.success(t("adminTab.toastVersionCreated")); setForm((f) => ({ ...f, version_label: "" })); }, onError: (e) => err(e, t("adminTab.couldNotCreateVersion")) }
              );
            }} disabled={create.isPending}>{t("adminTab.createSetCurrent")}</Button>
          </div>
        </CardContent>
      </Card>
      {versions.data?.map((v) => (
        <Card key={v.id}>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">{v.version_label}{v.is_current && <Badge variant="success">{t("adminTab.current")}</Badge>}</CardTitle>
              <p className="text-xs text-muted-foreground">{v.effective_date} · {Object.entries(v.params).map(([k, val]) => `${k}=${val}`).join(", ")}</p>
            </div>
            {!v.is_current && <Button variant="outline" size="sm" onClick={() => setCurrent.mutate(v.id, { onSuccess: () => toast.success(t("adminTab.toastSetCurrent")), onError: (e) => err(e, t("adminTab.couldNotSetCurrent")) })}>{t("adminTab.setCurrent")}</Button>}
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

/* ---------------- Quality ---------------- */
export function QualityTab() {
  const t = useT();
  const dash = useQualityDashboard();
  const feedback = useQualityFeedback();
  const lowAcc = useLowAccuracy();
  const resolve = useResolveFeedback();

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("adminTab.openFeedback")} value={dash.data?.open_feedback_count ?? 0} />
        <Stat label={t("adminTab.lowAccuracy")} value={dash.data?.low_accuracy_question_count ?? 0} />
        <Stat label={t("adminTab.missingExplanation")} value={dash.data?.missing_explanation_count ?? 0} />
        <Stat label={t("adminTab.disputed")} value={dash.data?.disputed_question_count ?? 0} />
      </div>

      <Card>
        <CardHeader><CardTitle>{t("adminTab.openFeedbackTitle")}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {feedback.isLoading && <p className="text-sm text-muted-foreground">{t("adminTab.loading")}</p>}
          {feedback.data?.items.length === 0 && <p className="text-sm text-muted-foreground">{t("adminTab.noOpenFeedback")}</p>}
          {feedback.data?.items.map((f) => (
            <div key={f.id} className="flex items-start justify-between gap-3 rounded-md border p-2 text-sm">
              <div>
                <Badge variant="outline">{enumLabel(t, "feedbackType", f.feedback_type)}</Badge>
                {f.comment && <p className="mt-1 text-muted-foreground">{f.comment}</p>}
              </div>
              <div className="flex shrink-0 gap-2">
                <Button size="sm" variant="outline" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: f.id, status: "resolved" }, { onSuccess: () => toast.success(t("adminTab.toastResolved")), onError: (e) => err(e, t("adminTab.couldNotResolve")) })}>{t("adminTab.resolve")}</Button>
                <Button size="sm" variant="ghost" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: f.id, status: "wont_fix" }, { onSuccess: () => toast.message(t("adminTab.toastWontFix")), onError: (e) => err(e, t("adminTab.couldNotUpdate")) })}>{t("adminTab.wontFix")}</Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("adminTab.lowAccuracyTitle")}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {lowAcc.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("adminTab.noneFlagged")}</p>}
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
  const t = useT();
  const [action, setAction] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const logs = useAuditLogs(action, offset);

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-4">
          <Select value={action ?? ANY} onValueChange={(v) => { setOffset(0); setAction(v === ANY ? null : v); }}>
            <SelectTrigger className="w-52"><SelectValue placeholder={t("adminTab.allActions")} /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>{t("adminTab.allActions")}</SelectItem>
              {AUDIT_ACTIONS.map((a) => <SelectItem key={a} value={a}>{enumLabel(t, "auditAction", a)}</SelectItem>)}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
      {logs.isLoading && <Loading label={t("adminTab.loadingAudit")} />}
      {logs.isError && <ErrorState message={t("adminTab.loadFailedAudit")} onRetry={() => logs.refetch()} />}
      {logs.data && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="px-4 py-2 font-medium">{t("adminTab.colWhen")}</th>
                  <th className="px-4 py-2 font-medium">{t("adminTab.colAction")}</th>
                  <th className="px-4 py-2 font-medium">{t("adminTab.colEntity")}</th>
                  <th className="px-4 py-2 font-medium">{t("adminTab.colDetails")}</th>
                </tr>
              </thead>
              <tbody>
                {logs.data.items.map((l) => (
                  <tr key={l.id} className="border-b last:border-0 align-top">
                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{fmtDate(l.occurred_at)}</td>
                    <td className="px-4 py-2"><Badge variant="outline">{enumLabel(t, "auditAction", l.action)}</Badge></td>
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
          <span className="text-muted-foreground">{t("adminTab.nEntries", { n: logs.data.total })}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - logs.data!.limit))}>{t("common.previous")}</Button>
            <Button variant="outline" size="sm" disabled={offset + logs.data.limit >= logs.data.total} onClick={() => setOffset((o) => o + logs.data!.limit)}>{t("common.next")}</Button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Reports ---------------- */
export function ReportsTab() {
  const t = useT();
  const [window, setWindow] = useState<30 | 90>(30);
  const report = useReportSummary(window);

  if (report.isLoading) return <Loading label={t("adminTab.loadingReport")} />;
  if (report.isError) return <ErrorState message={t("adminTab.loadFailedReport")} onRetry={() => report.refetch()} />;
  const r = report.data!;

  return (
    <div className="space-y-6">
      <div className="flex gap-1">
        {([30, 90] as const).map((w) => (
          <Button key={w} variant={window === w ? "default" : "outline"} size="sm" onClick={() => setWindow(w)}>{w}d</Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("adminTab.activeUsers")} value={r.active_users} />
        <Stat label={t("adminTab.practiceSessions")} value={r.practice_session_count} />
        <Stat label={t("adminTab.examSessions")} value={r.exam_session_count} />
        <Stat label={t("adminTab.overallAccuracy")} value={fmtPct(r.accuracy)} />
        <Stat label={t("adminTab.totalAnswers")} value={r.total_answers} />
        <Stat label={t("adminTab.publishedQuestions")} value={r.published_question_count} />
        <Stat label={t("adminTab.usedQuestions")} value={r.used_question_count} />
        <Stat label={t("adminTab.bankUsage")} value={fmtPct(r.question_bank_usage_pct / 100)} />
      </div>
      <Card>
        <CardHeader><CardTitle>{t("adminTab.topErrorQuestions")}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {r.top_error_questions.length === 0 && <p className="text-sm text-muted-foreground">{t("adminTab.none")}</p>}
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
    <Card className="p-4">
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </Card>
  );
}
