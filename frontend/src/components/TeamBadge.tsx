import type { CSSProperties } from "react";
import { getTeamColor, visibleRingColor } from "@/lib/teamColors";

const MIN_FONT_SIZE = 12;

/**
 * A team's colour and abbreviation. Used instead of club crests, which are
 * copyrighted and need their owners' consent.
 */
export default function TeamBadge({ name, size = 52 }: { name: string; size?: number }) {
  const { primary, abbr } = getTeamColor(name);
  const style = {
    "--team": primary,
    "--team-ring": visibleRingColor(primary),
    width: size,
    height: size,
    borderRadius: Math.round(size * 0.27),
    fontSize: Math.max(MIN_FONT_SIZE, Math.round(size * 0.27)),
  } as CSSProperties;
  return <span className="team-badge" role="img" aria-label={name} style={style}>{abbr}</span>;
}
