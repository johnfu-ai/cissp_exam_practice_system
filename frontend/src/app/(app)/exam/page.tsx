"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ExamStartForm } from "@/features/exam/start-form";
import { ExamHistoryPanel } from "@/features/exam/history-panel";

export default function ExamPage() {
  return (
    <div>
      <PageHeader
        title="Mock exams"
        description="Train your exam pace with fixed-length and adaptive (CAT) mock exams."
      />
      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">New exam</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
        <TabsContent value="new">
          <ExamStartForm />
        </TabsContent>
        <TabsContent value="history">
          <ExamHistoryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
