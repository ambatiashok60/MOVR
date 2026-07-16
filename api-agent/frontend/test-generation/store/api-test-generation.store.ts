import { Injectable, signal } from '@angular/core';

import { ApiScenarioTableRow } from '../models/api-scenario-table.model';
import { ApiTestGenerationResult, GenerationEvent, GenerationJob } from '../models/api-test-generation.model';

@Injectable({ providedIn: 'root' })
export class ApiTestGenerationStore {
  readonly scenarios = signal<ApiScenarioTableRow[]>([]);
  readonly selectedScenarioIds = signal<string[]>([]);
  readonly selectedScenarioId = signal<string | null>(null);
  readonly activeJob = signal<GenerationJob | null>(null);
  readonly events = signal<GenerationEvent[]>([]);
  readonly generatedResult = signal<ApiTestGenerationResult | null>(null);
  readonly isGeneratingScenarios = signal(false);
  readonly generatingCodeForId = signal<string | null>(null);
  readonly pendingApprovalRow = signal<ApiScenarioTableRow | null>(null);
  readonly error = signal<string | null>(null);
}
