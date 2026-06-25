import { ExamReview } from "@/features/exam/review";

export default function ExamReviewPage({ params }: { params: { id: string } }) {
  return <ExamReview sessionId={params.id} />;
}
