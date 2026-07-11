import { CommonModule } from '@angular/common';
import { Component, OnInit, Signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DropdownModule } from 'primeng/dropdown';
import { InputTextModule } from 'primeng/inputtext';
import { TabViewModule } from 'primeng/tabview';
import { TreeModule } from 'primeng/tree';
import { TreeNode } from 'primeng/api';

import { AiWorkspaceFacade } from './store/ai-workspace.facade';
import { AiFileNode } from './models/workspace.model';
import { BranchOption, RepositoryOption } from './services/workspace.service';

import { WorkspaceHeaderComponent } from './components/workspace-header/workspace-header.component';
import { WorkspaceSelectorComponent } from './components/workspace-selector/workspace-selector.component';
import { ModeToggleComponent } from './components/mode-toggle/mode-toggle.component';
import { ConversationComponent } from './components/conversation/conversation.component';
import { ChatInputComponent, QuickAction } from './components/chat-input/chat-input.component';
import { ContextPanelComponent } from './components/context-panel/context-panel.component';
import { SelectedFilesPanelComponent } from './components/selected-files-panel/selected-files-panel.component';
import { ExecutionTimelineComponent } from './components/execution-timeline/execution-timeline.component';
import { AgentPlanComponent } from './components/agent-plan/agent-plan.component';
import { ReviewPanelComponent, FileDecisionEvent } from './components/review-panel/review-panel.component';
import { PromptLibraryComponent } from './components/prompt-library/prompt-library.component';
import {
  AiWorkspaceSettingsComponent,
  SettingsSaveEvent,
} from './components/ai-workspace-settings/ai-workspace-settings.component';
import { SessionListComponent } from './components/session-list/session-list.component';
import { PromptTemplate } from './models/prompt.model';

const QUICK_ACTIONS: QuickAction[] = [
  { label: 'Explain this code', icon: 'pi pi-book', promptTemplate: (f) => `Explain ${f ?? 'the selected file'}` },
  {
    label: 'Refactor module',
    icon: 'pi pi-sync',
    promptTemplate: (f) => `Refactor ${f ?? 'this module'} and improve error handling.`,
  },
  {
    label: 'Add logging',
    icon: 'pi pi-file-edit',
    promptTemplate: (f) => `Add structured logging to ${f ?? 'the selected file'}.`,
  },
  {
    label: 'Generate tests',
    icon: 'pi pi-check-square',
    promptTemplate: (f) => `Generate unit tests for ${f ?? 'the selected file'}.`,
  },
];

@Component({
  selector: 'app-ai-workspace',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    DropdownModule,
    InputTextModule,
    TabViewModule,
    TreeModule,
    WorkspaceHeaderComponent,
    WorkspaceSelectorComponent,
    ModeToggleComponent,
    ConversationComponent,
    ChatInputComponent,
    ContextPanelComponent,
    SelectedFilesPanelComponent,
    ExecutionTimelineComponent,
    AgentPlanComponent,
    ReviewPanelComponent,
    PromptLibraryComponent,
    AiWorkspaceSettingsComponent,
    SessionListComponent,
  ],
  templateUrl: './ai-workspace.component.html',
  styleUrl: './ai-workspace.component.scss',
})
export class AiWorkspaceComponent implements OnInit {
  readonly quickActions = QUICK_ACTIONS;
  selectedFilePath: string | null = null;
  leftPanelTab: 'explorer' | 'history' | 'prompts' = 'explorer';
  prefillValue: string | null = null;

  readonly treeNodes: Signal<TreeNode[]> = computed(() =>
    this.facade.store.fileTree().map((node) => this.toTreeNode(node)),
  );

  constructor(readonly facade: AiWorkspaceFacade) {}

  ngOnInit(): void {
    this.facade.init();
  }

  refresh(): void {
    this.facade.refreshFileTree();
  }

  onRepositoryChange(repository: RepositoryOption | null): void {
    if (repository) this.facade.selectRepository(repository);
  }

  onBranchChange(branch: BranchOption | null): void {
    if (branch) this.facade.selectBranch(branch);
  }

  onFileSelect(event: { node: TreeNode }): void {
    if (!event.node.leaf) return;
    this.selectedFilePath = event.node.data as string;
    this.facade.addContextFile(this.selectedFilePath);
  }

  onTabChange(index: number): void {
    this.leftPanelTab = index === 0 ? 'explorer' : index === 1 ? 'history' : 'prompts';
    if (this.leftPanelTab === 'prompts' && !this.facade.store.prompts().length) {
      this.facade.loadPrompts();
    }
  }

  onPromptSelected(prompt: PromptTemplate): void {
    this.prefillValue = prompt.body;
  }

  onFileDecision(event: FileDecisionEvent): void {
    this.facade.setFileDecision(event.fileId, event.decision);
  }

  onSettingsSave(event: SettingsSaveEvent): void {
    this.facade.saveSettings(event.selectedModelId, event.enabledToolIds, event.preferences);
    this.facade.toggleSettings();
  }

  toTreeNode(node: AiFileNode): TreeNode {
    return {
      key: node.id,
      label: node.name,
      data: node.path,
      icon: node.type === 'folder' ? 'pi pi-folder' : 'pi pi-file',
      leaf: node.type === 'file',
      children: node.children?.map((c) => this.toTreeNode(c)),
    };
  }
}
