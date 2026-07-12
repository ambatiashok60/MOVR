import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, OnDestroy, SimpleChanges } from '@angular/core';

import { ApiScenarioTableComponent } from '../components/api-scenario-table/api-scenario-table.component';
import { MockPlanReviewComponent } from '../components/mock-plan-review/mock-plan-review.component';
import { ApiScenarioTableRow } from '../models/api-scenario-table.model';
import { SprintApiStory } from '../models/api-scenario.model';
import { ApiTestGenerationFacade } from '../store/api-test-generation.facade';

/**
 * Thin feature container. The host owns story/repository/branch selection; this component
 * owns only API-scenario generation and the API table block.
 */
@Component({
  selector: 'app-api-test-gen',
  standalone: true,
  imports: [CommonModule, ApiScenarioTableComponent, MockPlanReviewComponent],
  templateUrl: './api-test-gen.component.html',
  styleUrl: './api-test-gen.component.scss',
})
export class ApiTestGenComponent implements OnChanges, OnDestroy {
  @Input() selectedStory: SprintApiStory | null = null;
  @Input() tenantId: number | string = 1;
  @Input() repoPath = '';
  @Input() branch = '';
  @Input() additionalContext = '';

  constructor(readonly facade: ApiTestGenerationFacade) {}

  ngOnChanges(_: SimpleChanges): void {
    this.facade.setContext({
      story: this.selectedStory,
      tenantId: this.tenantId,
      repoPath: this.repoPath,
      branch: this.branch,
      additionalContext: this.additionalContext,
    });
  }

  ngOnDestroy(): void { this.facade.destroy(); }
  generateScenarios(): void { this.facade.generateScenarios(); }
  generateCode(row: ApiScenarioTableRow): void { this.facade.generateCode(row); }
  openScenario(row: ApiScenarioTableRow): void { this.facade.openScenario(row); }

  // HOST APP: connect these to the existing editor/confirmation flows when available.
  editScenario(_: ApiScenarioTableRow): void {}
  deleteScenario(_: ApiScenarioTableRow): void {}
}
