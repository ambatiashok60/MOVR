import { CommonModule } from '@angular/common';
import { Component, Input, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, finalize } from 'rxjs';

import {
  ApiScenarioSelection,
  GenerateApiTestCodeRequest,
  GenerationEvent,
  GenerationJob,
  ApiTestGenerationResult,
} from '../models/api-test-generation.model';
import {
  ApiScenario,
  ApiScenarioGenerationResult,
  GenerateApiScenariosRequest,
  SprintApiStory,
} from '../models/api-scenario.model';
import { ApiTestGenerationService } from '../services/api-test-generation.service';

@Component({
  selector: 'app-api-test-gen',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './api-test-gen.component.html',
  styleUrl: './api-test-gen.component.scss',
})
export class ApiTestGenComponent implements OnDestroy {
  @Input() stories: SprintApiStory[] = [];
  @Input() tenantId: number | string = 1;

  repoPath = '';
  branch = '';
  additionalContext = '';
  selectedStory: SprintApiStory | null = null;
  scenarioSelections: ApiScenarioSelection[] = [];
  activeTaskId: string | null = null;
  activeJob: GenerationJob | null = null;
  events: GenerationEvent[] = [];
  generatedResult: ApiTestGenerationResult | null = null;
  isGeneratingScenarios = false;
  isGeneratingTests = false;
  errorMessage: string | null = null;

  private eventSubscription?: Subscription;

  constructor(private readonly service: ApiTestGenerationService) {}

  ngOnDestroy(): void {
    this.eventSubscription?.unsubscribe();
  }

  selectStory(story: SprintApiStory): void {
    this.selectedStory = story;
    this.scenarioSelections = [];
    this.generatedResult = null;
    this.events = [];
    this.errorMessage = null;
  }

  generateScenarios(): void {
    if (!this.selectedStory || !this.repoPath.trim()) return;

    const payload: GenerateApiScenariosRequest = {
      user_story_hierarchy_id: this.selectedStory.user_story_hierarchy_id,
      user_story_id: this.selectedStory.user_story_id,
      tenant_id: this.tenantId,
      repo_path: this.repoPath.trim(),
      story_title: this.selectedStory.title,
      story_description: this.selectedStory.summary,
      acceptance_criteria: this.selectedStory.acceptance_criteria,
      additional_context: this.additionalContext || null,
      branch: this.branch || null,
    };

    this.errorMessage = null;
    this.isGeneratingScenarios = true;
    this.service
      .generateApiScenarios(payload)
      .pipe(finalize(() => (this.isGeneratingScenarios = false)))
      .subscribe({
        next: (queued) => {
          this.activeTaskId = queued.task_id;
          this.watchTask(queued.task_id, 'scenario');
        },
        error: () => {
          this.errorMessage = 'Unable to queue API scenario generation.';
        },
      });
  }

  generateSelectedTests(): void {
    const selected = this.scenarioSelections.filter((item) => item.selected);
    if (!this.selectedStory || !this.repoPath.trim() || !selected.length) return;

    this.errorMessage = null;
    this.generatedResult = null;
    this.isGeneratingTests = true;
    this.generateScenarioTest(selected[0].scenario, selected[0].target);
  }

  generateOne(selection: ApiScenarioSelection): void {
    if (!this.selectedStory || !this.repoPath.trim()) return;

    this.errorMessage = null;
    this.generatedResult = null;
    this.isGeneratingTests = true;
    this.generateScenarioTest(selection.scenario, selection.target);
  }

  abort(): void {
    if (!this.activeTaskId) return;
    this.service.abort(this.activeTaskId).subscribe({
      next: (job) => (this.activeJob = job),
      error: () => (this.errorMessage = 'Unable to abort the active generation job.'),
    });
  }

  toggleScenario(selection: ApiScenarioSelection): void {
    selection.selected = !selection.selected;
  }

  private generateScenarioTest(scenario: ApiScenario, target = scenario.execution_target): void {
    if (!this.selectedStory) return;

    const payload: GenerateApiTestCodeRequest = {
      user_story_hierarchy_id: this.selectedStory.user_story_hierarchy_id,
      api_scenario_id: scenario.api_scenario_id,
      scenario_name: scenario.scenario_name,
      scenario_steps: scenario.scenario_steps,
      tenant_id: this.tenantId,
      repo_path: this.repoPath.trim(),
      story_id: this.selectedStory.user_story_id,
      method: scenario.method,
      endpoint: scenario.endpoint,
      service_name: scenario.service_name,
      execution_target: target,
      assertions: scenario.assertions,
      branch: this.branch || null,
      run_validation: true,
      additional_context: this.additionalContext || null,
    };

    this.service
      .generateApiTestCode(payload)
      .pipe(finalize(() => (this.isGeneratingTests = false)))
      .subscribe({
        next: (queued) => {
          this.activeTaskId = queued.task_id;
          this.watchTask(queued.task_id, 'test');
        },
        error: () => {
          this.errorMessage = 'Unable to queue API test generation.';
        },
      });
  }

  private watchTask(taskId: string, mode: 'scenario' | 'test'): void {
    this.eventSubscription?.unsubscribe();
    this.events = [];
    this.eventSubscription = this.service.streamEvents(taskId).subscribe({
      next: (event) => {
        this.events = [...this.events, event];
        if (event.event_type === 'completed' || event.event_type === 'failed' || event.event_type === 'aborted') {
          this.refreshJob(taskId, mode);
        }
      },
      error: () => {
        this.refreshJob(taskId, mode);
      },
    });
  }

  private refreshJob(taskId: string, mode: 'scenario' | 'test'): void {
    this.service.getJob(taskId).subscribe({
      next: (job) => {
        this.activeJob = job;
        if (mode === 'scenario') {
          const result = this.service.extractScenarioResult(job);
          if (result) this.applyScenarioResult(result);
        } else if (job.result) {
          this.generatedResult = job.result as ApiTestGenerationResult;
        }
      },
      error: () => {
        this.errorMessage = 'Unable to refresh generation job status.';
      },
    });
  }

  private applyScenarioResult(result: ApiScenarioGenerationResult): void {
    this.scenarioSelections = result.scenarios.map((scenario) => ({
      scenario,
      selected: false,
      target: scenario.execution_target,
    }));
  }
}
