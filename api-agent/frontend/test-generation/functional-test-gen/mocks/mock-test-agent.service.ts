import { Injectable } from '@angular/core';
import { Observable, delay, of } from 'rxjs';

import {
  FunctionalGenerationResult,
  FunctionalTestCase,
  GenerateFunctionalCodeRequest,
  GenerateFunctionalScenariosRequest,
} from '../models/functional-test-generation.model';
import { TestAgentService } from '../services/test-agent.service';
import { MOCK_FUNCTIONAL_TEST_CASES } from './functional-test-generation.fixtures';

@Injectable()
export class MockTestAgentService extends TestAgentService {
  override generateScenarios(_: GenerateFunctionalScenariosRequest): Observable<FunctionalTestCase[]> {
    return of(MOCK_FUNCTIONAL_TEST_CASES.map((item) => ({ ...item }))).pipe(delay(650));
  }

  override generateCode(payload: GenerateFunctionalCodeRequest): Observable<FunctionalGenerationResult> {
    return of<FunctionalGenerationResult>({ testCaseId: payload.test_case_id, status: 'completed', filesChanged: ['e2e/soh-records.spec.ts'], diffSummary: `Added Playwright coverage for ${payload.test_case_id}`, validation: { syntax: 'passed', execution: 'notRun' }, needsReview: false }).pipe(delay(700));
  }
}
