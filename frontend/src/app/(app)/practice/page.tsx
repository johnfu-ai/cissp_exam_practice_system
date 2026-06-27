"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ResumePanel } from "@/features/practice/resume-panel";
import { CreateSessionForm } from "@/features/practice/create-session-form";
import { useT } from "@/lib/i18n/provider";

export default function PracticePage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        eyebrow={t("practice.eyebrow")}
        title={t("practice.title")}
        description={t("practice.description")}
      />
      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">{t("practice.newSession")}</TabsTrigger>
          <TabsTrigger value="resume">{t("practice.resume")}</TabsTrigger>
        </TabsList>
        <TabsContent value="new" className="pt-2">
          <CreateSessionForm />
        </TabsContent>
        <TabsContent value="resume" className="pt-2">
          <ResumePanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
