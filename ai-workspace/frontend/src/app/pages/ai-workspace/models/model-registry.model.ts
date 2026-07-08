export interface ModelCapabilities {
  supportsTools: boolean;
  supportsStreaming: boolean;
  supportsVision: boolean;
}

export interface ModelLimits {
  contextWindowTokens: number;
  maxOutputTokens: number;
}

export interface ModelDefinition {
  id: string;
  displayName: string;
  providerId: string;
  capabilities: ModelCapabilities;
  limits: ModelLimits;
  isDefault?: boolean;
}

export interface Provider {
  id: string;
  displayName: string;
  models: ModelDefinition[];
}

export interface RuntimeConfiguration {
  selectedModelId: string;
  temperature?: number;
  maxOutputTokens?: number;
}

export interface ModelRegistry {
  models: ModelDefinition[];
  runtime: RuntimeConfiguration;
}
