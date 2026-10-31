import { getTeamColor, readableTextOn } from "@/lib/teamColors";

const MIN_FONT_SIZE = 8;

/**
 * A team's colour and abbreviation. Used instead of club crests, which are
 * copyrighted and need their owners' consent.
 */
export default function TeamBadge({ name, size = 52 }: { name: string; size?: number }) {
  const { primary, abbr } = getTeamColor(name);
  return (
    <span
      role="img"
      aria-label={name}
      style={{
        width: size, height: size, flexShrink: 0,
        borderRadius: Math.round(size * 0.27),
        background: primary,
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.14)",
        display: "grid", placeItems: "center",
        color: readableTextOn(primary),
        fontSize: Math.max(MIN_FONT_SIZE, Math.round(size * 0.27)),
        fontWeight: 800, letterSpacing: "0.03em", lineHeight: 1,
      }}
    >
      {abbr}
    </span>
  );
}
