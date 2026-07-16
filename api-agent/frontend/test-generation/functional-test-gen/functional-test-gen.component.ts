import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges } from '@angular/core';

import { SprintApiStory } from '../models/api-scenario.model';
import { FunctionalTestCase } from './models/functional-test-generation.model';
import { FunctionalTestGenerationFacade } from './store/functional-test-generation.facade';

@Component({ selector: 'app-functional-test-gen', standalone: true, imports: [CommonModule], templateUrl: './functional-test-gen.component.html', styleUrl: './functional-test-gen.component.scss' })
export class FunctionalTestGenComponent implements OnChanges {
  @Input() selectedStory: SprintApiStory | null = null;
  @Input() tenantId: number | string = 1;
  @Input() repoPath = '';
  @Input() branch = '';
  constructor(readonly facade: FunctionalTestGenerationFacade) {}
  ngOnChanges(): void { this.facade.setContext({ story: this.selectedStory, tenantId: this.tenantId, repoPath: this.repoPath, branch: this.branch }); }
  generateScenarios(): void { this.facade.generateScenarios(); }
  open(item: FunctionalTestCase): void { this.facade.open(item); }
  generateCode(item: FunctionalTestCase): void { this.facade.generateCode(item); }
}
