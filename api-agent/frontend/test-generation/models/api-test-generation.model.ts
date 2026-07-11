import { ApiScenario, ExecutionTarget } from './api-scenario.model';

export type ApiGenerationTaskStatus =
  | 'queued'
  | 'running'
  | 'aborting'
  | 'aborted'
  | 'completed'
  | 'failed';

export interface QueuedTask {
  queued: boolean;
  task_id: string;
}

export interface SourceSnippet {
  path: string;
  reason: string;
  content: string;
}

export interface ExistingTestExample {
  path: string;
  target?: string | null;
  framework?: string | null;
  strategy?: string | null;
  relevance_score: number;
  signals: string[];
  content: string;
}

export interface DependencyCandidate {
  name: string;
  type_name?: string | null;
  source_file: string;
  dependency_kind: string;
  reason: string;
}

export interface MockStubPlan {
  strategy?: string | null;
  reused_helpers: string[];
  dependencies_to_mock: DependencyCandidate[];
  generated_stubs: string[];
  external_services_to_stub: string[];
  warnings: string[];
  risk_level: string;
  approval_required: boolean;
  approval_reasons: string[];
  runtime_signals: string[];
  provisioning_actions: string[];
  auth_strategy?: string | null;
}

export interface GeneratedFile {
  path: string;
  operation: string;
  test_target: string;
  summary: string;
}

export interface ValidationResult {
  passed: boolean;
  command?: string | null;
  summary: string;
  details: string[];
}

export interface GenerationBudgetReport {
  enforcement_mode: 'review' | 'strict' | string;
  review_required: boolean;
  exceeded_thresholds: string[];
  usage: {
    llm_calls: number;
    tool_calls: number;
    repository_reads: number;
    repair_attempts: number;
    prompt_chars: number;
    completion_chars: number;
    elapsed_seconds: number;
  };
}

export interface GenerateApiTestCodeRequest {
  user_story_hierarchy_id: number;
  api_scenario_id: string;
  scenario_name: string;
  scenario_steps: string[];
  tenant_id?: number | string | null;
  repo_path: string;
  story_id?: string | null;
  method?: string | null;
  endpoint?: string | null;
  service_name?: string | null;
  execution_target: ExecutionTarget;
  assertions: string[];
  branch?: string | null;
  run_validation: boolean;
  additional_context?: string | null;
  approve_high_risk_mocks?: boolean;
}

export interface ApiTestGenerationResult {
  task_id: string;
  user_story_hierarchy_id: number;
  api_scenario_id: string;
  generated_files: GeneratedFile[];
  validation?: ValidationResult | null;
  summary: string;
  strategy_name?: string | null;
  strategy_confidence?: string | null;
  strategy_reasons: string[];
  reused_examples: ExistingTestExample[];
  source_files_used: SourceSnippet[];
  mock_stub_plan?: MockStubPlan | null;
  warnings: string[];
  needs_review?: boolean;
  review_reasons?: string[];
  budget?: GenerationBudgetReport | null;
}

export interface GenerationEvent {
  task_id: string;
  event_type: string;
  stage: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface GenerationJob {
  task_id: string;
  key?: string | null;
  task_type: string;
  status: ApiGenerationTaskStatus;
  stage: string;
  request_payload: Record<string, unknown>;
  result?: ApiScenarioGenerationResult | ApiTestGenerationResult | null;
  error?: string | null;
  abort_requested: boolean;
  created_at: string;
  updated_at: string;
  events: GenerationEvent[];
}

export interface ApiScenarioSelection {
  scenario: ApiScenario;
  selected: boolean;
  target: ExecutionTarget;
}
