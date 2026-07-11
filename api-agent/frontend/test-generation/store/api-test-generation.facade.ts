import { Injectable } from '@angular/core';
import { Subscription } from 'rxjs';

import { SprintApiStory } from '../models/api-scenario.model';
import { ApiScenarioTableRow, toApiScenarioTableRow } from '../models/api-scenario-table.model';
import { GenerateApiTestCodeRequest } from '../models/api-test-generation.model';
import { ApiTestGenerationEventsService } from '../services/api-test-generation-events.service';
import { ApiTestGenerationService } from '../services/api-test-generation.service';
import { ApiTestGenerationSelectors } from './api-test-generation.selectors';
import { ApiTestGenerationStore } from './api-test-generation.store';

export interface ApiTestGenerationContext {
  story: SprintApiStory | null;
  tenantId: number | string;
  repoPath: string;
  branch: string;
  additionalContext?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiTestGenerationFacade {
  private context: ApiTestGenerationContext = {
    story: null,
    tenantId: 1,
    repoPath: '',
    branch: '',
  };
  private eventSubscription?: Subscription;

  constructor(
    readonly store: ApiTestGenerationStore,
    readonly selectors: ApiTestGenerationSelectors,
    private readonly api: ApiTestGenerationService,
    private readonly events: ApiTestGenerationEventsService,
  ) {}

  setContext(context: ApiTestGenerationContext): void {
    this.context = context;
  }

  generateScenarios(): void {
    const { story, tenantId, repoPath, branch, additionalContext } = this.context;
    if (!story || !repoPath.trim()) {
      this.store.error.set('Select a story and repository before generating API scenarios.');
      return;
    }

    this.store.error.set(null);
    this.store.isGeneratingScenarios.set(true);
    this.api.generateApiScenarios({
      user_story_hierarchy_id: story.user_story_hierarchy_id,
      user_story_id: story.user_story_id,
      tenant_id: tenantId,
      repo_path: repoPath.trim(),
      story_title: story.title,
      story_description: story.summary,
      acceptance_criteria: story.acceptance_criteria,
      additional_context: additionalContext || null,
      branch: branch || null,
    }).subscribe({
      next: ({ task_id }) => this.watch(task_id, 'scenarios'),
      error: () => {
        this.store.isGeneratingScenarios.set(false);
        this.store.error.set('Unable to queue API scenario generation.');
      },
    });
  }

  generateCode(row: ApiScenarioTableRow, approved = false): void {
    const { story, tenantId, repoPath, branch, additionalContext } = this.context;
    if (!story || !repoPath.trim()) return;

    const scenario = row.source;
    const payload: GenerateApiTestCodeRequest = {
      user_story_hierarchy_id: story.user_story_hierarchy_id,
      api_scenario_id: scenario.api_scenario_id,
      scenario_name: scenario.scenario_name,
      scenario_steps: scenario.scenario_steps,
      tenant_id: tenantId,
      repo_path: repoPath.trim(),
      story_id: story.user_story_id,
      method: scenario.method,
      endpoint: scenario.endpoint,
      service_name: scenario.service_name,
      execution_target: row.target,
      assertions: scenario.assertions,
      branch: branch || null,
      run_validation: true,
      additional_context: additionalContext || null,
      approve_high_risk_mocks: approved,
    };

    this.store.error.set(null);
    this.store.generatingCodeForId.set(row.id);
    this.api.generateApiTestCode(payload).subscribe({
        next: ({ task_id }) => this.watch(task_id, 'code'),
        error: () => {
          this.store.generatingCodeForId.set(null);
          this.store.error.set('Unable to queue API test-code generation.');
        },
      });
  }

  setSelection(ids: string[]): void {
    this.store.selectedScenarioIds.set(ids);
  }

  openScenario(row: ApiScenarioTableRow): void {
    this.store.selectedScenarioId.set(row.id);
  }

  destroy(): void {
    this.eventSubscription?.unsubscribe();
  }

  private watch(taskId: string, mode: 'scenarios' | 'code'): void {
    this.eventSubscription?.unsubscribe();
    this.store.events.set([]);
    this.eventSubscription = this.events.stream(taskId).subscribe({
      next: (event) => {
        this.store.events.update((events) => [...events, event]);
        if (['completed', 'failed', 'aborted'].includes(event.event_type)) {
          this.refresh(taskId, mode);
        }
      },
      error: () => this.refresh(taskId, mode),
    });
  }

  private refresh(taskId: string, mode: 'scenarios' | 'code'): void {
    this.api.getJob(taskId).subscribe({
      next: (job) => {
        this.store.activeJob.set(job);
        if (mode === 'scenarios') {
          this.store.isGeneratingScenarios.set(false);
          const result = this.api.extractScenarioResult(job);
          if (result) this.store.scenarios.set(result.scenarios.map(toApiScenarioTableRow));
        } else if (job.result && !('scenarios' in job.result)) {
          const codeResult = job.result;
          this.store.generatingCodeForId.set(null);
          this.store.generatedResult.set(codeResult);
          this.store.pendingApprovalRow.set(
            codeResult.mock_stub_plan?.approval_required && !codeResult.generated_files.length
              ? this.store.scenarios().find((row) => row.id === codeResult.api_scenario_id) ?? null
              : null,
          );
        }
      },
      error: () => {
        this.store.isGeneratingScenarios.set(false);
        this.store.generatingCodeForId.set(null);
        this.store.error.set('Unable to refresh generation status.');
      },
    });
  }

  approveAndContinue(): void {
    const row = this.store.pendingApprovalRow();
    if (!row) return;
    this.store.pendingApprovalRow.set(null);
    this.generateCode(row, true);
  }
}
