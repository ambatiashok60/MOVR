import { ApiScenario, ExecutionTarget } from './api-scenario.model';

export type ApiScenarioStatus = 'Draft' | 'Generating' | 'Generated' | 'Failed' | string;

export interface ApiScenarioDependency {
  label: string;
  kind: 'database' | 'authentication' | 'service' | 'other';
}

/** Stable, display-only contract consumed by the portable table component. */
export interface ApiScenarioTableRow {
  id: string;
  name: string;
  operation: string;
  method: string;
  type: string;
  target: ExecutionTarget;
  dependencies: ApiScenarioDependency[];
  priority: string;
  status: ApiScenarioStatus;
  source: ApiScenario;
}

export function toApiScenarioTableRow(scenario: ApiScenario): ApiScenarioTableRow {
  return {
    id: scenario.api_scenario_id,
    name: scenario.scenario_name,
    operation: scenario.endpoint || scenario.service_name || '-',
    method: scenario.method || '-',
    type: scenario.scenario_type,
    target: scenario.execution_target,
    // The scenario-generation API does not currently return structured dependencies.
    // HOST APP: enrich this array from story/repository analysis if that data already exists.
    dependencies: [],
    priority: scenario.priority,
    status: 'Draft',
    source: scenario,
  };
}
