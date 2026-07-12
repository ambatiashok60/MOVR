import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { ApiTestGenComponent } from '@api-test-generation/api-test-gen/api-test-gen.component';
import { FunctionalTestGenComponent } from '@api-test-generation/functional-test-gen/functional-test-gen.component';
import { MOCK_STORY } from '@api-test-generation/mocks/api-test-generation.fixtures';
import { SprintApiStory } from '@api-test-generation/models/api-scenario.model';

/**
 * Host page for the Test Gen area (design-review scaffold).
 *
 * Owns what the WorkTop host will own in production: repository/branch
 * selection and the sprint story list. The embedded TestGenerationComponent
 * (from api-agent/frontend/test-generation) owns the Functional/API tabs,
 * scenario table, drawer, and generation flows.
 */
@Component({
  selector: 'app-test-generation-page',
  standalone: true,
  imports: [CommonModule, ApiTestGenComponent, FunctionalTestGenComponent],
  templateUrl: './test-generation-page.component.html',
  styleUrl: './test-generation-page.component.scss',
})
export class TestGenerationPageComponent {
  readonly mode: 'functional' | 'api';
  readonly repository = signal('wfm-repo');
  readonly branch = signal('feature/BNWSE-1974');
  readonly repoPath = signal('/repos/wfm-repo');
  readonly stories = signal<SprintApiStory[]>([MOCK_STORY]);
  readonly selectedStory = signal<SprintApiStory | null>(MOCK_STORY);

  constructor(route: ActivatedRoute) {
    this.mode = route.snapshot.data['testGenerationMode'] === 'api' ? 'api' : 'functional';
  }

  selectStory(story: SprintApiStory): void {
    this.selectedStory.set(this.selectedStory() === story ? null : story);
  }
}
