export const qk = {
  domains: ["domains"] as const,
  books: ["books"] as const,
  chapters: (bookId: string) => ["books", bookId, "chapters"] as const,
  tags: ["tags"] as const,
  session: (id: string) => ["practice", "session", id] as const,
  question: (sessionId: string, position: number) =>
    ["practice", "session", sessionId, "question", position] as const,
  summary: (id: string) => ["practice", "session", id, "summary"] as const,
};
