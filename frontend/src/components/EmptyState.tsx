interface Props {
  title?: string;
  message?: string;
}

export default function EmptyState({
  title = "No matches found",
  message = "There are no upcoming fixtures available right now. Check back later.",
}: Props) {
  return (
    <div className="card flex flex-col items-center justify-center gap-4 py-16 px-8 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--primary-soft)] border border-[var(--primary-edge)]">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-[var(--primary-text)]">
          <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div>
        <h3 className="font-semibold text-[var(--ink)]">{title}</h3>
        <p className="mt-1 text-sm text-[var(--muted)] max-w-xs">{message}</p>
      </div>
    </div>
  );
}
