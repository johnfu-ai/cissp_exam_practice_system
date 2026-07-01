import { QuestionDetailView } from "@/features/questions/detail";

export default async function QuestionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuestionDetailView questionId={id} />;
}
