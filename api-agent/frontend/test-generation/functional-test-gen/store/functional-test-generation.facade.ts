import { Injectable } from '@angular/core';

import { SprintApiStory } from '../../models/api-scenario.model';
import { FunctionalTestCase } from '../models/functional-test-generation.model';
import { TestAgentService } from '../services/test-agent.service';
import { FunctionalTestGenerationStore } from './functional-test-generation.store';

export interface FunctionalContext { story: SprintApiStory | null; tenantId: number | string; repoPath: string; branch: string; }

@Injectable({ providedIn: 'root' })
export class FunctionalTestGenerationFacade {
  private context: FunctionalContext = { story: null, tenantId: 1, repoPath: '', branch: '' };
  constructor(readonly store: FunctionalTestGenerationStore, private readonly api: TestAgentService) {}

  setContext(context: FunctionalContext): void { this.context = context; }
  generateScenarios(): void {
    const { story, tenantId, repoPath, branch } = this.context;
    if (!story || !repoPath.trim()) { this.store.error.set('Select a story and repository before generating functional tests.'); return; }
    this.store.error.set(null); this.store.generatingScenarios.set(true);
    this.api.generateScenarios({ user_story_id: story.user_story_id, story_title: story.title, story_description: story.summary ?? '', acceptance_criteria: story.acceptance_criteria, tenant_id: tenantId, repo_path: repoPath, branch: branch || null }).subscribe({
      next: (items) => { this.store.testCases.set(items); this.store.openId.set(items[0]?.id ?? null); this.store.generatingScenarios.set(false); },
      error: () => { this.store.generatingScenarios.set(false); this.store.error.set('Unable to generate functional test cases.'); },
    });
  }
  open(item: FunctionalTestCase): void { this.store.openId.set(item.id); }
  toggle(id: string): void { this.store.selectedIds.update((ids) => ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]); }
  generateCode(item: FunctionalTestCase): void {
    const { tenantId, repoPath, branch } = this.context;
    this.store.generatingCodeForId.set(item.id); this.store.error.set(null);
    this.api.generateCode({ test_case_id: item.id, tenant_id: tenantId, repo_path: repoPath, branch: branch || null, run_validation: true }).subscribe({
      next: (result) => { this.store.result.set(result); this.store.generatingCodeForId.set(null); this.store.testCases.update((items) => items.map((entry) => entry.id === item.id ? { ...entry, status: result.needsReview ? 'Needs Review' : 'Generated' } : entry)); },
      error: () => { this.store.generatingCodeForId.set(null); this.store.error.set('Unable to generate Playwright code.'); },
    });
  }
  opened(): FunctionalTestCase | null { return this.store.testCases().find((item) => item.id === this.store.openId()) ?? null; }
}
