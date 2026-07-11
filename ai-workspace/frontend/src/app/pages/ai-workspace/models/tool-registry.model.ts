export interface ToolSchema {
  /** JSON-schema-shaped parameter definition, kept loose here — the backend owns validation. */
  parameters: Record<string, unknown>;
}

export interface ToolCapabilities {
  readsFiles: boolean;
  writesFiles: boolean;
  requiresConfirmation: boolean;
}

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  capabilities: ToolCapabilities;
  schema: ToolSchema;
}

export interface RuntimeToolSelection {
  enabledToolIds: string[];
}

export interface ToolRegistry {
  tools: ToolDefinition[];
  runtime: RuntimeToolSelection;
}
