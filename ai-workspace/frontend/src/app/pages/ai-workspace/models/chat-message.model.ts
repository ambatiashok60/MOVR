export type ChatRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  /** Present when an assistant message resulted from an Agent Mode run. */
  executionId?: string;
}
