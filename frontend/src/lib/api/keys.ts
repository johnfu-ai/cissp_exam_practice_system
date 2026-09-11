export const qk = {
  domains: ["domains"] as const,
  books: ["books"] as const,
  chapters: (bookId: string) => ["books", bookId, "chapters"] as const,
  tags: ["tags"] as const,
  me: () => ["auth", "me"] as const,
  preferences: () => ["preferences"] as const,
  etl: {
    datasets: ["etl", "datasets"] as const,
    run: (id: string) => ["etl", "run", id] as const,
    mappings: (datasetSlug?: string | null) =>
      ["etl", "mappings", datasetSlug ?? "all"] as const,
  },
  kpDomains: (kpId: string) => ["knowledge-points", kpId, "domains"] as const,
  questions: {
    list: (filters: Record<string, unknown>) => ["questions", "list", filters] as const,
    detail: (id: string) => ["questions", "detail", id] as const,
    revisions: (id: string) => ["questions", id, "revisions"] as const,
    feedback: (id: string) => ["questions", id, "feedback"] as const,
  },
  blueprints: ["blueprints"] as const,
  knowledgePoints: ["knowledge-points"] as const,
  admin: {
    users: (q: Record<string, unknown>) => ["admin", "users", q] as const,
    classes: ["admin", "classes"] as const,
    classMembers: (id: string) => ["admin", "classes", id, "members"] as const,
    classReport: (id: string, windowDays: number) =>
      ["admin", "classes", id, "report", windowDays] as const,
    catParams: ["admin", "cat-params"] as const,
    qualityDashboard: ["admin", "quality", "dashboard"] as const,
    feedback: (q: Record<string, unknown>) => ["admin", "quality", "feedback", q] as const,
    lowAccuracy: ["admin", "quality", "low-accuracy"] as const,
    audit: (q: Record<string, unknown>) => ["admin", "audit", q] as const,
    report: (windowDays: number) => ["admin", "report", windowDays] as const,
    languageCoverage: ["admin", "language-coverage"] as const,
  },
};
