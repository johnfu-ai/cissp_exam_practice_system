export const qk = {
  domains: ["domains"] as const,
  books: ["books"] as const,
  chapters: (bookId: string) => ["books", bookId, "chapters"] as const,
  tags: ["tags"] as const,
  session: (id: string) => ["practice", "session", id] as const,
  question: (sessionId: string, position: number) =>
    ["practice", "session", sessionId, "question", position] as const,
  summary: (id: string) => ["practice", "session", id, "summary"] as const,
  analytics: {
    dashboard: ["analytics", "dashboard"] as const,
    domains: ["analytics", "domains"] as const,
    trend: (windowDays: number) => ["analytics", "trend", windowDays] as const,
    weakAreas: ["analytics", "weak-areas"] as const,
    errorTypes: ["analytics", "error-types"] as const,
    recommendation: ["analytics", "recommendation"] as const,
    report: ["analytics", "report"] as const,
  },
  exam: {
    session: (id: string) => ["exam", "session", id] as const,
    question: (id: string, position: number) =>
      ["exam", "session", id, "question", position] as const,
    next: (id: string) => ["exam", "session", id, "next"] as const,
    report: (id: string) => ["exam", "session", id, "report"] as const,
    review: (id: string) => ["exam", "session", id, "review"] as const,
    history: ["exam", "history"] as const,
  },
  etl: {
    datasets: ["etl", "datasets"] as const,
    run: (id: string) => ["etl", "run", id] as const,
  },
  questions: {
    list: (filters: Record<string, unknown>) => ["questions", "list", filters] as const,
    detail: (id: string) => ["questions", "detail", id] as const,
    revisions: (id: string) => ["questions", id, "revisions"] as const,
    feedback: (id: string) => ["questions", id, "feedback"] as const,
  },
  blueprints: ["blueprints"] as const,
  knowledgePoints: ["knowledge-points"] as const,
};
