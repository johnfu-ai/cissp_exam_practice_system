import { QuestionDetailView } from "@/features/questions/detail";

export default function QuestionPage({ params }: { params: { id: string } }) {
  return <QuestionDetailView questionId={params.id} />;
}
