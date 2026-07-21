import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  FunctionalGenerationResult,
  FunctionalTestCase,
  GenerateFunctionalCodeRequest,
  GenerateFunctionalScenariosRequest,
} from '../models/functional-test-generation.model';

export const TEST_AGENT_PREFIX = '/api/playwright';

@Injectable({ providedIn: 'root' })
export class TestAgentService {
  constructor(private readonly http: HttpClient) {}

  generateScenarios(payload: GenerateFunctionalScenariosRequest): Observable<FunctionalTestCase[]> {
    return this.http.post<FunctionalTestCase[]>(`${TEST_AGENT_PREFIX}/scenarios`, payload);
  }

  generateCode(payload: GenerateFunctionalCodeRequest): Observable<FunctionalGenerationResult> {
    return this.http.post<FunctionalGenerationResult>(`${TEST_AGENT_PREFIX}/generate`, payload);
  }
}
