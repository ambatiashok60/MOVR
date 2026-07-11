import { ApiScenario, ApiScenarioDependencyRef, ExecutionTarget } from './api-scenario.model';

export type ApiScenarioStatus = 'Draft' | 'Generating' | 'Generated' | 'Failed' | string;

export type ApiScenarioDependency = ApiScenarioDependencyRef;

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
    dependencies: scenario.dependencies ?? [],
    priority: scenario.priority,
    status: 'Draft',
    source: scenario,
  };
}
