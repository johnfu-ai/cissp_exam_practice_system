export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main
      className="flex min-h-screen items-center justify-center px-4 py-8"
      style={{
        background:
          "linear-gradient(180deg, hsl(var(--hero-from)) 0%, hsl(var(--hero-to)) 100%)",
      }}
    >
      <div className="w-full max-w-md">{children}</div>
    </main>
  );
}
