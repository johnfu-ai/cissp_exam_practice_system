import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function Field({
  children,
  icon: Icon,
  label,
  htmlFor,
  className,
}: {
  children: React.ReactNode;
  icon?: LucideIcon;
  label?: string;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">
          {label}
        </label>
      )}
      {Icon ? (
        <div className="field-surface flex h-10 items-center gap-2 rounded-md border border-input bg-background px-3 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
          <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          {children}
        </div>
      ) : (
        <div>{children}</div>
      )}
    </div>
  );
}
