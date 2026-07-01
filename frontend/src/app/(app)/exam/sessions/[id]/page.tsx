import { ExamRunner } from "@/features/exam/runner";

export default async function ExamSessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamRunner sessionId={id} />;
}
