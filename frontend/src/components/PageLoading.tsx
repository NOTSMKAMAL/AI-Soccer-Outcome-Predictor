/** Neutral full-page state while Firebase resolves whether anyone is signed in. */
export default function PageLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-[var(--muted)]">Loading…</p>
    </div>
  );
}
