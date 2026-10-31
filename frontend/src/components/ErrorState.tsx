interface Props {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: Props) {
  return (
    <div className="card flex flex-col items-center justify-center gap-4 py-16 px-8 text-center border-[var(--danger-edge)]">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--danger-soft)] border border-[var(--danger-edge)]">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-[var(--danger)]">
          <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div>
        <h3 className="font-semibold text-[var(--ink)]">{title}</h3>
        {message && (
          <p className="mt-1 text-sm text-[var(--muted)] max-w-sm font-mono">{message}</p>
        )}
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost text-sm py-2 px-4">
          Try again
        </button>
      )}
    </div>
  );
}
