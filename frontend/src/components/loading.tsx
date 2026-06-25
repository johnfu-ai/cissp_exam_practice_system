import { Skeleton } from "@/components/ui/skeleton";

export function Loading({ label }: { label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-busy="true">
      {label && <p className="text-sm text-muted-foreground">{label}</p>}
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
