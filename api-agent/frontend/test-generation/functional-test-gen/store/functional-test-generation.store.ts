import { Injectable, signal } from '@angular/core';

import { FunctionalGenerationResult, FunctionalTestCase } from '../models/functional-test-generation.model';

@Injectable({ providedIn: 'root' })
export class FunctionalTestGenerationStore {
  readonly testCases = signal<FunctionalTestCase[]>([]);
  readonly selectedIds = signal<string[]>([]);
  readonly openId = signal<string | null>(null);
  readonly generatingScenarios = signal(false);
  readonly generatingCodeForId = signal<string | null>(null);
  readonly result = signal<FunctionalGenerationResult | null>(null);
  readonly error = signal<string | null>(null);
}
