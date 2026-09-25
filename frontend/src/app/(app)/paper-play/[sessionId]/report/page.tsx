import { PaperReportView } from "@/features/paper-play/report-view";

export default async function PaperReportPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <PaperReportView sessionId={sessionId} />;
}
