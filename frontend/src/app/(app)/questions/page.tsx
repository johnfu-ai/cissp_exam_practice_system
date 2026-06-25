"use client";

import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { RequirePermission } from "@/components/require-permission";
import { QuestionList } from "@/features/questions/list";

export default function QuestionsPage() {
  return (
    <div>
      <PageHeader
        title="Questions"
        description="Browse, filter, edit, and review the question bank."
        actions={
          <RequirePermission perm="question:write">
            <Button asChild>
              <Link href="/questions/new">New question</Link>
            </Button>
          </RequirePermission>
        }
      />
      <QuestionList />
    </div>
  );
}
