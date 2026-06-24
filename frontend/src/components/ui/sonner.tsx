"use client";
import { Toaster as SonnerToaster, toast } from "sonner";

function Toaster(props: React.ComponentProps<typeof SonnerToaster>) {
  return (
    <SonnerToaster
      position="top-right"
      toastOptions={{
        classNames: {
          toast: "group rounded-md border bg-background text-foreground shadow-lg",
          error: "border-destructive/50",
          success: "border-success/50",
        },
      }}
      {...props}
    />
  );
}

export { Toaster, toast };
