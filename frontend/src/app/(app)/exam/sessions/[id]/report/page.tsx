import { ExamReport } from "@/features/exam/report";

export default async function ExamReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamReport sessionId={id} />;
}
