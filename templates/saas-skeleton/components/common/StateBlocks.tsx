import { Loader2, AlertCircle } from "lucide-react";

export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="mt-4 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function ErrorState({
  message = "Something went wrong",
  retry,
}: {
  message?: string;
  retry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-destructive/20 bg-destructive/5 p-12 text-center">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <p className="mt-4 text-sm text-destructive">{message}</p>
      {retry && (
        <button
          onClick={retry}
          className="mt-4 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
        >
          Try again
        </button>
      )}
    </div>
  );
}
