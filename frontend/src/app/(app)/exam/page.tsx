"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ExamStartForm } from "@/features/exam/start-form";
import { ExamHistoryPanel } from "@/features/exam/history-panel";
import { useT } from "@/lib/i18n/provider";

export default function ExamPage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={t("exam.eyebrow")}
        title={t("exam.title")}
        description={t("exam.description")}
      />
      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">{t("exam.newExam")}</TabsTrigger>
          <TabsTrigger value="history">{t("exam.history")}</TabsTrigger>
        </TabsList>
        <TabsContent value="new" className="mt-6">
          <ExamStartForm />
        </TabsContent>
        <TabsContent value="history" className="mt-6">
          <ExamHistoryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
