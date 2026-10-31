export interface InsightChip {
  label: string;
  text: string;
}

const MAX_INSIGHTS = 4;
const MIN_SENTENCE_LENGTH = 30;

// Checked in order; the first topic a sentence mentions becomes its heading.
// Specific topics come before broad ones: a sentence naming a top scorer
// usually also mentions goals, and "Key players" is the more useful heading.
const TOPICS: Array<{ label: string; pattern: RegExp }> = [
  { label: "Head-to-head",    pattern: /head[- ]to[- ]head|\bh2h\b|previous meetings|last met/i },
  { label: "Key players",     pattern: /scorer|striker|goalkeeper|captain|injur|suspen|line-?up|starting xi/i },
  { label: "Recent form",     pattern: /\bform\b|win rate|last (five|\d+) (matches|games)|unbeaten|winless|streak/i },
  { label: "League position", pattern: /standings|\btable\b|\bposition|\bpoints?\b|\b\d+(st|nd|rd|th)\b/i },
  { label: "Goals",           pattern: /\bgoals?\b|scored|conceded|clean sheet|\bxg\b/i },
];

function labelFor(sentence: string, index: number): string {
  return TOPICS.find((t) => t.pattern.test(sentence))?.label ?? `Insight ${index + 1}`;
}

/**
 * Split Gemini's reasoning into up to four headed insights. Each heading comes
 * from what its sentence actually mentions, not from its position — Gemini does
 * not order its sentences by topic.
 */
export function extractInsightChips(reasoning: string): InsightChip[] {
  const sentences = reasoning
    .replace(/\n+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > MIN_SENTENCE_LENGTH);

  return sentences.slice(0, MAX_INSIGHTS).map((text, i) => ({ label: labelFor(text, i), text }));
}
