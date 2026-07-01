import { ExamReview } from "@/features/exam/review";

export default async function ExamReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamReview sessionId={id} />;
}
