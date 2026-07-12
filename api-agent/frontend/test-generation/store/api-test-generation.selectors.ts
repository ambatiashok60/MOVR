import { Injectable, computed } from '@angular/core';

import { ApiTestGenerationStore } from './api-test-generation.store';

@Injectable({ providedIn: 'root' })
export class ApiTestGenerationSelectors {
  constructor(private readonly store: ApiTestGenerationStore) {}

  readonly hasScenarios = computed(() => this.store.scenarios().length > 0);
  readonly selectedScenario = computed(() =>
    this.store.scenarios().find((row) => row.id === this.store.selectedScenarioId()) ?? null,
  );
  readonly isBusy = computed(
    () => this.store.isGeneratingScenarios() || this.store.generatingCodeForId() !== null,
  );
}
