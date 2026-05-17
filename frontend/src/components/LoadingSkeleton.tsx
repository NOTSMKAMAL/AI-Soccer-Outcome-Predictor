export function MatchCardSkeleton() {
  return (
    <div className="card-glass p-5 animate-pulse">
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-full bg-white/5" />
          <div className="h-3 w-20 rounded bg-white/5" />
          <div className="h-2.5 w-10 rounded bg-white/5" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="h-3 w-6 rounded bg-white/5" />
          <div className="h-px w-8 bg-white/5" />
        </div>
        <div className="flex-1 flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-full bg-white/5" />
          <div className="h-3 w-20 rounded bg-white/5" />
          <div className="h-2.5 w-10 rounded bg-white/5" />
        </div>
      </div>
      <div className="mt-4 h-2.5 w-32 mx-auto rounded bg-white/5" />
      <div className="mt-4 h-10 w-full rounded-xl bg-white/5" />
    </div>
  );
}

export function PredictionSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="card-glass p-8 flex flex-col items-center gap-4">
        <div className="h-4 w-24 rounded bg-white/5" />
        <div className="h-10 w-48 rounded bg-white/5" />
        <div className="h-6 w-20 rounded-full bg-white/5" />
        <div className="h-3 w-full max-w-md rounded bg-white/5" />
        <div className="h-3 w-3/4 max-w-md rounded bg-white/5" />
        <div className="h-3 w-2/3 max-w-md rounded bg-white/5" />
      </div>
      <div className="card-glass p-6 space-y-3">
        <div className="h-4 w-32 rounded bg-white/5" />
        <div className="h-3 w-full rounded bg-white/5" />
        <div className="h-3 w-5/6 rounded bg-white/5" />
        <div className="h-3 w-4/6 rounded bg-white/5" />
      </div>
    </div>
  );
}
