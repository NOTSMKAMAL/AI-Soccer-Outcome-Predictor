export function MatchCardSkeleton() {
  return (
    <div className="card p-5 animate-pulse">
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 flex flex-col items-start gap-2">
          <div className="h-12 w-12 rounded-xl bg-[var(--surface-2)]" />
          <div className="h-3 w-20 rounded bg-[var(--surface-2)]" />
          <div className="h-2.5 w-10 rounded bg-[var(--surface-2)]" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="h-3 w-6 rounded bg-[var(--surface-2)]" />
          <div className="h-px w-8 bg-[var(--surface-2)]" />
        </div>
        <div className="flex-1 flex flex-col items-end gap-2">
          <div className="h-12 w-12 rounded-xl bg-[var(--surface-2)]" />
          <div className="h-3 w-20 rounded bg-[var(--surface-2)]" />
          <div className="h-2.5 w-10 rounded bg-[var(--surface-2)]" />
        </div>
      </div>
      <div className="mt-4 h-px w-full bg-[var(--surface-2)]" />
      <div className="mt-3 flex justify-between items-center">
        <div className="h-2.5 w-32 rounded bg-[var(--surface-2)]" />
        <div className="h-8 w-20 rounded-lg bg-[var(--surface-2)]" />
      </div>
    </div>
  );
}

export function PredictionSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="card p-8 flex flex-col items-center gap-4">
        <div className="h-4 w-24 rounded-full bg-[var(--surface-2)]" />
        <div className="h-10 w-48 rounded bg-[var(--surface-2)]" />
        <div className="h-6 w-20 rounded-full bg-[var(--surface-2)]" />
        <div className="h-3 w-full max-w-md rounded bg-[var(--surface-2)]" />
        <div className="h-3 w-3/4 max-w-md rounded bg-[var(--surface-2)]" />
        <div className="mt-2 h-3 w-full max-w-xs rounded-full bg-[var(--surface-2)]" />
      </div>
      <div className="card p-6 space-y-3">
        <div className="h-4 w-32 rounded bg-[var(--surface-2)]" />
        <div className="h-3 w-full rounded bg-[var(--surface-2)]" />
        <div className="h-3 w-5/6 rounded bg-[var(--surface-2)]" />
        <div className="h-3 w-4/6 rounded bg-[var(--surface-2)]" />
      </div>
    </div>
  );
}
