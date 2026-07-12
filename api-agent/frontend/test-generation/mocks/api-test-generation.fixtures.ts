import { ApiScenario, ApiScenarioGenerationResult, SprintApiStory } from '../models/api-scenario.model';
import {
  ApiTestGenerationResult,
  GenerationEvent,
  GenerationJob,
} from '../models/api-test-generation.model';

/**
 * Demo fixtures for the WorkTop "API Tests" design review.
 *
 * Everything here mirrors the real backend contract (worktop.api_agent schemas) so the
 * backend team can read these fixtures as an executable specification of what each
 * endpoint must return.
 */

export const MOCK_STORY: SprintApiStory = {
  user_story_hierarchy_id: 1974,
  user_story_id: 'BNWSE-1974',
  title: 'SOH Table - View, Filter, and Manage Statement of Health Records',
  summary:
    'As an HR admin I can view, filter, and manage Statement of Health records so that ' +
    'employee compliance is auditable.',
  sprint: 'Sprint 24',
  api_area: 'soh-records',
  status: 'Analyzed',
  acceptance_criteria: [
    'SOH records are returned for valid filter combinations',
    'An empty result set is returned when no records match',
    'Records can be filtered by employeeId',
    'Invalid employeeId values are rejected with a 400 error',
    'Pagination metadata is returned with every page',
    'Unauthenticated requests are rejected',
  ],
};

export const MOCK_SCENARIOS: ApiScenario[] = [
  {
    api_scenario_id: 'API_TC_001',
    scenario_name: 'Verify successful retrieval of SOH records with valid filters',
    scenario_type: 'positive',
    service_name: 'soh-service',
    method: 'GET',
    endpoint: '/api/soh-records',
    priority: 'P0',
    execution_target: 'both',
    reason: 'Core read path for the SOH table; highest-traffic endpoint in the story.',
    scenario_steps: [
      'Authenticate as an HR admin (bearer token)',
      'Call GET /api/soh-records with valid employee and status filters',
      'Read the paginated response body',
    ],
    assertions: [
      'Status code 200 OK',
      'Response schema matches SOHRecordsResponse',
      'Non-empty records returned',
      'Pagination metadata is correct',
    ],
    dependencies: [{ label: 'DB', kind: 'database' }],
  },
  {
    api_scenario_id: 'API_TC_002',
    scenario_name: 'Verify empty response when no SOH records exist',
    scenario_type: 'positive',
    service_name: 'soh-service',
    method: 'GET',
    endpoint: '/api/soh-records',
    priority: 'P1',
    execution_target: 'both',
    reason: 'Empty state drives the UI empty-state banner; must be a valid 200, not an error.',
    scenario_steps: [
      'Seed the database with zero matching records',
      'Call GET /api/soh-records with a filter that matches nothing',
    ],
    assertions: ['Status code 200 OK', 'records array is empty', 'totalCount is 0'],
    dependencies: [{ label: 'DB', kind: 'database' }],
  },
  {
    api_scenario_id: 'API_TC_003',
    scenario_name: 'Verify filter by employeeId',
    scenario_type: 'positive',
    service_name: 'soh-service',
    method: 'GET',
    endpoint: '/api/soh-records',
    priority: 'P1',
    execution_target: 'ci',
    reason: 'employeeId is the primary filter in acceptance criteria.',
    scenario_steps: [
      'Seed records for two employees',
      'Call GET /api/soh-records?employeeId=E-100',
    ],
    assertions: [
      'Status code 200 OK',
      'Every returned record belongs to employee E-100',
    ],
    dependencies: [{ label: 'DB', kind: 'database' }],
  },
  {
    api_scenario_id: 'API_TC_004',
    scenario_name: 'Verify invalid employeeId returns 400',
    scenario_type: 'negative',
    service_name: 'soh-service',
    method: 'GET',
    endpoint: '/api/soh-records',
    priority: 'P0',
    execution_target: 'both',
    reason: 'Input validation is an explicit acceptance criterion.',
    scenario_steps: ['Call GET /api/soh-records?employeeId=not-a-valid-id'],
    assertions: [
      'Status code 400 Bad Request',
      'Error body names the employeeId field',
    ],
    dependencies: [{ label: 'DB', kind: 'database' }],
  },
  {
    api_scenario_id: 'API_TC_005',
    scenario_name: 'Verify pagination metadata',
    scenario_type: 'contract',
    service_name: 'soh-service',
    method: 'GET',
    endpoint: '/api/soh-records',
    priority: 'P2',
    execution_target: 'both',
    reason: 'Pagination contract is consumed by the table component.',
    scenario_steps: [
      'Seed 45 records',
      'Call GET /api/soh-records?page=2&pageSize=20',
    ],
    assertions: [
      'Status code 200 OK',
      'page=2, pageSize=20, totalCount=45 in pagination metadata',
      'Response schema matches SOHRecordsResponse',
    ],
    dependencies: [{ label: 'DB', kind: 'database' }],
  },
  {
    api_scenario_id: 'API_TC_006',
    scenario_name: 'Verify authentication required',
    scenario_type: 'auth',
    service_name: 'soh-service',
    method: 'GET',
    endpoint: '/api/soh-records',
    priority: 'P0',
    execution_target: 'stage',
    reason: 'Security acceptance criterion; must run against real auth on stage.',
    scenario_steps: ['Call GET /api/soh-records without an Authorization header'],
    assertions: ['Status code 401 Unauthorized', 'No record data is leaked in the body'],
    dependencies: [{ label: 'Auth', kind: 'authentication' }],
  },
];

export const MOCK_SCENARIO_RESULT: ApiScenarioGenerationResult = {
  task_id: 'mock-scenarios-1',
  user_story_hierarchy_id: MOCK_STORY.user_story_hierarchy_id,
  user_story_id: MOCK_STORY.user_story_id,
  scenarios: MOCK_SCENARIOS,
  repo_findings: [
    'Detected Spring Boot 3 + RestAssured 5 (build.gradle)',
    'Endpoint GET /api/soh-records found in SohRecordsController.java',
    '12 existing API tests under src/test/java/api',
  ],
  warnings: [],
};

export const MOCK_CODE_RESULT: ApiTestGenerationResult = {
  task_id: 'mock-code-1',
  user_story_hierarchy_id: MOCK_STORY.user_story_hierarchy_id,
  api_scenario_id: 'API_TC_001',
  generated_files: [
    {
      path: 'src/test/java/api/soh/SohRecordsRetrievalApiTest.java',
      operation: 'created',
      test_target: 'both',
      summary: 'RestAssured integration test for GET /api/soh-records with valid filters',
    },
    {
      path: 'src/test/java/api/soh/support/SohRecordsTestData.java',
      operation: 'created',
      test_target: 'both',
      summary: 'Testcontainers seed data builder for SOH records',
    },
  ],
  validation: {
    passed: true,
    command: './gradlew test --tests SohRecordsRetrievalApiTest',
    summary: 'Compilation and dry-run validation passed.',
    details: ['BUILD SUCCESSFUL in 41s', '2 tests completed, 0 failed'],
  },
  summary:
    'Generated a RestAssured integration test that reuses the repository auth helper and ' +
    'Testcontainers profile; assertions cover status, schema, records, and pagination.',
  strategy_name: 'java_spring_rest_assured',
  strategy_confidence: 'high',
  strategy_reasons: [
    'RestAssured 5 present in build.gradle',
    'Existing tests extend BaseApiIntegrationTest',
  ],
  reused_examples: [
    {
      path: 'src/test/java/api/employee/EmployeeRecordsApiTest.java',
      target: 'ci',
      framework: 'restassured',
      strategy: 'java_spring_rest_assured',
      relevance_score: 0.86,
      signals: ['same controller package', 'same auth helper'],
      content: '// closest existing example (truncated for demo)',
    },
  ],
  source_files_used: [
    {
      path: 'src/main/java/com/worktop/soh/SohRecordsController.java',
      reason: 'Endpoint under test',
      content: '// controller source (truncated for demo)',
    },
  ],
  mock_stub_plan: {
    strategy: 'testcontainers',
    reused_helpers: ['BaseApiIntegrationTest', 'AuthTokenFactory'],
    dependencies_to_mock: [
      {
        name: 'sohRecordsRepository',
        type_name: 'SohRecordsRepository',
        source_file: 'src/main/java/com/worktop/soh/SohRecordsRepository.java',
        dependency_kind: 'database',
        reason: 'Seeded via Testcontainers PostgreSQL profile',
      },
    ],
    generated_stubs: [],
    external_services_to_stub: [],
    warnings: [],
    risk_level: 'low',
    approval_required: false,
    approval_reasons: [],
    runtime_signals: ['testcontainers profile detected'],
    provisioning_actions: ['Start PostgreSQL Testcontainer before the test class'],
    auth_strategy: 'Bearer token via AuthTokenFactory',
  },
  warnings: [],
  needs_review: false,
  review_reasons: [],
  budget: {
    enforcement_mode: 'review',
    review_required: false,
    exceeded_thresholds: [],
    usage: {
      llm_calls: 6,
      tool_calls: 11,
      repository_reads: 9,
      repair_attempts: 0,
      prompt_chars: 48_211,
      completion_chars: 9_874,
      elapsed_seconds: 38.4,
    },
  },
};

const now = () => new Date().toISOString();

export function mockEvents(taskId: string, kind: 'scenarios' | 'code'): GenerationEvent[] {
  const stages: Array<[string, string, string]> =
    kind === 'scenarios'
      ? [
          ['queued', 'queued', 'Task accepted'],
          ['running', 'scanning_repository', 'Scanning repository for API context'],
          ['progress', 'finding_api_endpoints', 'Found 14 endpoints, 12 existing API tests'],
          ['progress', 'generating_scenarios', 'Generating API test scenarios'],
          ['progress', 'scenario_value_analysis', '6 scenario(s): NEW_COVERAGE'],
          ['completed', 'completed', 'API scenarios generated'],
        ]
      : [
          ['queued', 'queued', 'Task accepted'],
          ['running', 'scanning_repository', 'Scanning repository for API test conventions'],
          ['progress', 'planning_mocks_and_stubs', 'Planning mocks, stubs, and fixtures'],
          ['progress', 'selecting_generation_strategy', 'Selected java_spring_rest_assured'],
          ['progress', 'generating_test_code', 'Generating repository-native API tests'],
          ['progress', 'validating', 'Compilation and dry-run validation passed'],
          ['completed', 'completed', 'API test generation completed'],
        ];
  return stages.map(([event_type, stage, message]) => ({
    task_id: taskId,
    event_type,
    stage,
    message,
    payload: {},
    created_at: now(),
  }));
}

export function mockJob(
  taskId: string,
  kind: 'scenarios' | 'code',
): GenerationJob {
  return {
    task_id: taskId,
    key: null,
    task_type: kind === 'scenarios' ? 'generate_api_scenarios' : 'generate_api_test_code',
    status: 'completed',
    stage: 'completed',
    request_payload: {},
    result:
      kind === 'scenarios'
        ? { ...MOCK_SCENARIO_RESULT, task_id: taskId }
        : { ...MOCK_CODE_RESULT, task_id: taskId },
    error: null,
    abort_requested: false,
    created_at: now(),
    updated_at: now(),
    events: mockEvents(taskId, kind),
  };
}
