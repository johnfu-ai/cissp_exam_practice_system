import { ExamRunner } from "@/features/exam/runner";

export default function ExamSessionPage({ params }: { params: { id: string } }) {
  return <ExamRunner sessionId={params.id} />;
}
