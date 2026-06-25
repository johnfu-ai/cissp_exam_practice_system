import { ExamReport } from "@/features/exam/report";

export default function ExamReportPage({ params }: { params: { id: string } }) {
  return <ExamReport sessionId={params.id} />;
}
