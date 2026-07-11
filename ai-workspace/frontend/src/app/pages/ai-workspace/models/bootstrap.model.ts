import { ModelRegistry } from './model-registry.model';
import { ToolRegistry } from './tool-registry.model';
import { WorkspaceInfo } from './workspace.model';

export interface FeatureFlags {
  [flagName: string]: boolean;
}

export interface UserPermissions {
  canRunAgent: boolean;
  canApplyChanges: boolean;
  canEditSettings: boolean;
}

export interface UserPreferences {
  defaultMode: 'ask' | 'agent';
  theme?: 'light' | 'dark' | 'system';
}

export interface PlannerConfig {
  maxPlanSteps: number;
}

export interface ExecutionConfig {
  sseEndpoint: string;
  pollIntervalMs?: number;
}

export interface TelemetryConfig {
  enabled: boolean;
  endpoint?: string;
}

/**
 * Single payload returned by GET /api/ai-workspace/bootstrap, fetched once when AI Workspace
 * loads so the frontend doesn't hardcode models/tools or make N separate startup calls.
 */
export interface BootstrapPayload {
  workspace?: WorkspaceInfo;
  models: ModelRegistry;
  tools: ToolRegistry;
  featureFlags: FeatureFlags;
  permissions: UserPermissions;
  preferences: UserPreferences;
  planner: PlannerConfig;
  execution: ExecutionConfig;
  telemetry: TelemetryConfig;
}
