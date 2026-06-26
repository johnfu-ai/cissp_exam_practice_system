"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ResumePanel } from "@/features/practice/resume-panel";
import { CreateSessionForm } from "@/features/practice/create-session-form";

export default function PracticePage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        eyebrow="Practice"
        title="Practice"
        description="Build and resume scoped practice sessions."
      />
      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">New session</TabsTrigger>
          <TabsTrigger value="resume">Resume</TabsTrigger>
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
