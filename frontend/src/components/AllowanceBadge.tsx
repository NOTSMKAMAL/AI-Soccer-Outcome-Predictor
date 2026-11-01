import { formatDailyReset } from "@/lib/dateUtils";
import type { PredictionAllowance } from "@/lib/types";

export function allowanceLabel(allowance: PredictionAllowance): string {
  if (allowance.unlimited) return "Unlimited";
  return `${allowance.remaining} of ${allowance.limit} predictions left today · Resets ${formatDailyReset()}`;
}

/** "X of 3 predictions left today · Resets today at 5:00 PM PDT", or "Unlimited" for the owner. */
export default function AllowanceBadge({ allowance }: { allowance: PredictionAllowance | null }) {
  if (!allowance) return null;
  return (
    <p role="status" className="text-xs" style={{ color: "var(--muted)" }}>
      {allowanceLabel(allowance)}
    </p>
  );
}
