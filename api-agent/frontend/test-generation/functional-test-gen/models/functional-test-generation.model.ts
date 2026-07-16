export type FunctionalTestStatus = 'Draft' | 'Generating' | 'Generated' | 'Needs Review' | 'Failed';
export type FunctionalPriority = 'P0' | 'P1' | 'P2';

export interface FunctionalTestCase {
  id: string;
  title: string;
  description: string;
  technique: string;
  priority: FunctionalPriority;
  status: FunctionalTestStatus;
  riskLevel: 'Low' | 'Normal' | 'High';
  owner: string | null;
  steps: string[];
  expectedResults: string[];
  linkedArtifacts: string[];
  lastUpdated: string;
}

export interface GenerateFunctionalScenariosRequest {
  user_story_id: string;
  story_title: string;
  story_description: string;
  acceptance_criteria: string[];
  tenant_id: number | string;
  repo_path: string;
  branch: string | null;
}

export interface GenerateFunctionalCodeRequest {
  test_case_id: string;
  tenant_id: number | string;
  repo_path: string;
  branch: string | null;
  run_validation: boolean;
}

export interface FunctionalGenerationResult {
  testCaseId: string;
  status: 'completed' | 'needs_review' | 'failed';
  filesChanged: string[];
  diffSummary: string;
  validation: { syntax: 'passed' | 'failed'; execution: 'passed' | 'failed' | 'notRun' };
  needsReview: boolean;
}
