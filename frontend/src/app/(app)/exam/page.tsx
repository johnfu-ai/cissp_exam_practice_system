"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ExamStartForm } from "@/features/exam/start-form";
import { ExamHistoryPanel } from "@/features/exam/history-panel";

export default function ExamPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow="Exam"
        title="Mock exams"
        description="Train your exam pace with fixed-length and adaptive (CAT) mock exams."
      />
      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">New exam</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
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
