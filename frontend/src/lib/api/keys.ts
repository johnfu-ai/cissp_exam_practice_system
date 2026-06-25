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
};
