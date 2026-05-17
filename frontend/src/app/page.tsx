import Link from "next/link";

/**
 * Public landing page — placeholder only.
 * Final visual design will be applied in a later pass.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-bold">AI Sports Predictor</h1>
      <p className="text-gray-500">
        Placeholder landing page — final design coming soon.
      </p>
      <div className="flex gap-4">
        <Link
          href="/auth"
          className="rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
        >
          Get started
        </Link>
        <Link
          href="/dashboard"
          className="rounded border px-4 py-2 hover:bg-gray-50"
        >
          Dashboard
        </Link>
      </div>
    </main>
  );
}
