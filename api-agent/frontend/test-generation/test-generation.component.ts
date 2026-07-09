import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { ApiTestGenComponent } from './api-test-gen/api-test-gen.component';
import { FunctionalTestGenComponent } from './functional-test-gen/functional-test-gen.component';
import { SprintApiStory } from './models/api-scenario.model';

type TestGenerationTab = 'functional' | 'api';

@Component({
  selector: 'app-test-generation',
  standalone: true,
  imports: [CommonModule, FunctionalTestGenComponent, ApiTestGenComponent],
  templateUrl: './test-generation.component.html',
  styleUrl: './test-generation.component.scss',
})
export class TestGenerationComponent {
  @Input() stories: SprintApiStory[] = [];
  @Input() tenantId: number | string = 1;

  activeTab: TestGenerationTab = 'functional';

  setTab(tab: TestGenerationTab): void {
    this.activeTab = tab;
  }
}
