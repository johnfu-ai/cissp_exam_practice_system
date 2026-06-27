"use client";

import {
  usePreferences,
  useUpdatePreferences,
  useUpdateInterfaceLanguage,
} from "@/lib/api/preferences";
import { useI18n, useT } from "@/lib/i18n/provider";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
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
    </div>
  );
}
