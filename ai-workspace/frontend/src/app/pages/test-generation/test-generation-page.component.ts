import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';

import { TestGenerationComponent } from '@api-test-generation/test-generation.component';
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
  imports: [CommonModule, TestGenerationComponent],
  templateUrl: './test-generation-page.component.html',
  styleUrl: './test-generation-page.component.scss',
})
export class TestGenerationPageComponent {
  readonly repository = signal('wfm-repo');
  readonly branch = signal('feature/BNWSE-1974');
  readonly repoPath = signal('/repos/wfm-repo');
  readonly stories = signal<SprintApiStory[]>([MOCK_STORY]);
  readonly selectedStory = signal<SprintApiStory | null>(MOCK_STORY);

  selectStory(story: SprintApiStory): void {
    this.selectedStory.set(this.selectedStory() === story ? null : story);
  }
}
