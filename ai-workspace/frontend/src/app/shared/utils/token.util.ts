export function formatTokenCount(tokens: number): string {
  if (tokens < 1000) return `${tokens}`;
  return `${(tokens / 1000).toFixed(1)}k`;
}

/**
 * Very rough client-side estimate for UI feedback only (e.g. "about N tokens" while typing).
 * The authoritative count comes from context_budget_manager.py on the backend — never use
 * this for anything that enforces a real budget.
 */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}
