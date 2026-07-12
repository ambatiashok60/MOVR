import { Component } from '@angular/core';

import { ApiTestGenComponent } from '../api-test-gen/api-test-gen.component';
import { SprintApiStory } from '../models/api-scenario.model';

/** REFERENCE ONLY: adapt these fields to the existing Test Generation container/store. */
@Component({
  selector: 'app-host-test-generation-example',
  standalone: true,
  imports: [ApiTestGenComponent],
  templateUrl: './host-test-generation.example.html',
})
export class HostTestGenerationExampleComponent {
  // HOST APP: bind these to the existing functional-test page selections.
  activeTab: 'functional' | 'api' = 'api';
  selectedStory: SprintApiStory | null = null;
  tenantId: number | string = 1;
  repositoryPath = '';
  selectedBranch = '';
}
