export interface SelectedFile {
  path: string;
  isPriority: boolean;
}

export interface TokenUsage {
  inputTokens: number;
  reservedOutputTokens: number;
  budgetTokens: number;
}

export interface ContextSummary {
  sessionId: string;
  fileCount: number;
  tokenCount: number;
  files: SelectedFile[];
  tokenUsage?: TokenUsage;
}
