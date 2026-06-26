import { PageHeader } from "@/components/page-header";
import { QuestionEditor } from "@/features/questions/editor";

export default function NewQuestionPage() {
  return (
    <div>
      <PageHeader eyebrow="Content" title="New question" crumbs={["Questions"]} description="Create a draft question." />
      <QuestionEditor />
    </div>
  );
}
