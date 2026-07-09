export type ExecutionTarget = 'ci' | 'stage' | 'both';

export interface ApiScenario {
  api_scenario_id: string;
  scenario_name: string;
  scenario_type: string;
  service_name?: string | null;
  method?: string | null;
  endpoint?: string | null;
  priority: string;
  execution_target: ExecutionTarget;
  reason: string;
  scenario_steps: string[];
  assertions: string[];
}

export interface GenerateApiScenariosRequest {
  user_story_hierarchy_id: number;
  user_story_id?: string | null;
  tenant_id?: number | string | null;
  repo_path: string;
  story_title?: string | null;
  story_description?: string | null;
  acceptance_criteria: string[];
  additional_context?: string | null;
  branch?: string | null;
}

export interface ApiScenarioGenerationResult {
  task_id: string;
  user_story_hierarchy_id: number;
  user_story_id?: string | null;
  scenarios: ApiScenario[];
  repo_findings: string[];
  warnings: string[];
}

export interface SprintApiStory {
  user_story_hierarchy_id: number;
  user_story_id: string;
  title: string;
  summary?: string;
  sprint?: string;
  api_area?: string;
  status?: string;
  acceptance_criteria: string[];
}
