"use client";

import { useState } from "react";
import { Lock } from "lucide-react";
import {
  usePreferences,
  useUpdatePreferences,
  useUpdateInterfaceLanguage,
} from "@/lib/api/preferences";
import { apiJson, ApiError } from "@/lib/api";
import { useI18n, useT } from "@/lib/i18n/provider";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/sonner";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import type { LanguageCode, LanguageMode } from "@/lib/api/types";

export function SettingsView() {
  const t = useT();
  const { setLocale } = useI18n();
  const prefs = usePreferences();
  const updateContent = useUpdatePreferences();
  const updateInterface = useUpdateInterfaceLanguage();

  const interfaceLanguage: LanguageCode = prefs.data?.interface_language ?? "en";
  const contentMode: LanguageMode = prefs.data?.language_mode ?? "en";

  function onInterface(value: string) {
    const l = value as LanguageCode;
    // Switch the active render locale immediately; the hook persists to the
    // backend + writes the ui_lang cookie on success.
    setLocale(l);
    updateInterface.mutate(l);
  }

  function onContent(value: string) {
    updateContent.mutate(value as LanguageMode);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        eyebrow={t("settings.eyebrow")}
        title={t("settings.title")}
        description={t("settings.description")}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.interfaceTitle")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("settings.interfaceDesc")}</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="ui-lang">{t("settings.interfaceTitle")}</Label>
            <Select value={interfaceLanguage} onValueChange={onInterface}>
              <SelectTrigger id="ui-lang" className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">{t("lang.en")}</SelectItem>
                <SelectItem value="zh">{t("lang.zh")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.contentTitle")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("settings.contentDesc")}</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="content-lang">{t("settings.contentTitle")}</Label>
            <Select value={contentMode} onValueChange={onContent}>
              <SelectTrigger id="content-lang" className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">{t("lang.en")}</SelectItem>
                <SelectItem value="zh">{t("lang.zh")}</SelectItem>
                <SelectItem value="bilingual">{t("lang.bilingual")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <ChangePasswordCard />
    </div>
  );
}

function ChangePasswordCard() {
  const t = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError(t("settings.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      await apiJson("/api/auth/password", {
        method: "PUT",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      toast.success(t("settings.passwordChanged"));
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError(t("settings.passwordIncorrect"));
      } else {
        toast.error(t("settings.passwordIncorrect"));
      }
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0";

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.changePasswordTitle")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("settings.changePasswordDesc")}</p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <Field label={t("settings.currentPassword")} htmlFor="cp-current" icon={Lock}>
            <Input
              id="cp-current"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className={inputCls}
              required
            />
          </Field>
          <Field label={t("settings.newPassword")} htmlFor="cp-new" icon={Lock}>
            <Input
              id="cp-new"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              className={inputCls}
              minLength={8}
              required
            />
          </Field>
          <Field label={t("settings.confirmPassword")} htmlFor="cp-confirm" icon={Lock}>
            <Input
              id="cp-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={inputCls}
              minLength={8}
              required
            />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" size="pill" disabled={busy}>
            {busy ? t("settings.updating") : t("settings.changePasswordTitle")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
