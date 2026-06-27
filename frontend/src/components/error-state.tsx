import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  const t = useT();
  return (
    <Alert variant="destructive">
      <AlertTitle>{title ?? t("common.errorTitle")}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      {onRetry && (
        <div className="mt-3">
          <Button variant="outline" size="sm" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        </div>
      )}
    </Alert>
  );
}
