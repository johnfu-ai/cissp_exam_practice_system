import { PaperPlayer } from "@/features/paper-play/player";

export default async function PaperPlayPage({
  params,
  searchParams,
}: {
  params: Promise<{ sessionId: string }>;
  searchParams: Promise<{ kind?: string; paper?: string }>;
}) {
  const { sessionId } = await params;
  const { kind, paper } = await searchParams;
  return (
    <PaperPlayer
      sessionId={sessionId}
      kind={kind === "exam" ? "exam" : "practice"}
      paperId={paper}
    />
  );
}
