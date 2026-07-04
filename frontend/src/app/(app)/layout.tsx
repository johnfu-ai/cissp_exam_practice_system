import { RequireAuth } from "@/components/require-auth";
import { AppSidebar } from "@/components/app-sidebar";
import { LegalFooter } from "@/components/legal-footer";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex min-h-screen bg-canvas">
        <AppSidebar />
        <main className="flex-1 overflow-y-auto px-8 py-6">
          {children}
          <LegalFooter />
        </main>
      </div>
    </RequireAuth>
  );
}
