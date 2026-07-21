import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RepoAgentWorkspaceComponent } from './repo-agent/pages/repo-agent-workspace.component';

@Component({
  selector: 'ra-root',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RepoAgentWorkspaceComponent],
  template: `<ra-repo-agent-workspace></ra-repo-agent-workspace>`,
})
export class AppComponent {}
