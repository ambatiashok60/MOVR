import { Injectable } from '@angular/core';

import { AiWorkspaceMode } from '../models/ai-workspace.model';
import { UserPreferences } from '../models/bootstrap.model';
import { AgentService } from '../services/agent.service';
import { AiWorkspaceService } from '../services/ai-workspace.service';
import { BootstrapService } from '../services/bootstrap.service';
import { ContextBuilderService } from '../services/context-builder.service';
import { ConversationService } from '../services/conversation.service';
import { ModelRegistryService } from '../services/model-registry.service';
import { PromptLibraryService } from '../services/prompt-library.service';
import { ReviewService } from '../services/review.service';
import { SessionService } from '../services/session.service';
import { SettingsService } from '../services/settings.service';
import { ToolRegistryService } from '../services/tool-registry.service';
import { BranchOption, RepositoryOption, WorkspaceService } from '../services/workspace.service';
import { AiWorkspaceSelectors } from './ai-workspace.selectors';
import { AiWorkspaceStore } from './ai-workspace.store';

/**
 * The only thing components should depend on for AI Workspace behavior. Components read state
 * via `facade.store` / `facade.selectors` and call methods here rather than injecting the
 * individual services directly — keeps request orchestration (loading sequences, what triggers
 * what) in one place instead of scattered across components.
 */
@Injectable({ providedIn: 'root' })
export class AiWorkspaceFacade {
  constructor(
    readonly store: AiWorkspaceStore,
    readonly selectors: AiWorkspaceSelectors,
    private readonly bootstrapService: BootstrapService,
    private readonly workspaceService: WorkspaceService,
    private readonly sessionService: SessionService,
    private readonly conversationService: ConversationService,
    private readonly contextBuilderService: ContextBuilderService,
    private readonly aiWorkspaceService: AiWorkspaceService,
    private readonly agentService: AgentService,
    private readonly reviewService: ReviewService,
    private readonly promptLibraryService: PromptLibraryService,
    private readonly modelRegistryService: ModelRegistryService,
    private readonly toolRegistryService: ToolRegistryService,
    private readonly settingsService: SettingsService,
  ) {}

  init(): void {
    this.bootstrapService.getBootstrap().subscribe((payload) => {
      this.store.bootstrap.set(payload);
      if (payload.workspace) this.store.workspace.set(payload.workspace);
    });
    this.workspaceService.getRepositories().subscribe((repos) => {
      this.store.repositories.set(repos);
      if (repos.length) this.selectRepository(repos[0]);
    });
  }

  selectRepository(repository: RepositoryOption): void {
    this.store.selectedRepository.set(repository);
    this.store.branches.set([]);
    this.store.selectedBranch.set(null);

    this.workspaceService.getBranches(repository.id).subscribe((branches) => {
      this.store.branches.set(branches);
      const defaultBranch = branches.find((b) => b.isDefault) ?? branches[0] ?? null;
      if (defaultBranch) this.selectBranch(defaultBranch);
    });
  }

  selectBranch(branch: BranchOption): void {
    this.store.selectedBranch.set(branch);
    this.startOrResumeSession();

    const repository = this.store.selectedRepository();
    if (repository) {
      this.workspaceService.getFiles(repository.id, branch.name).subscribe((nodes) => this.store.fileTree.set(nodes));
    }
  }

  refreshFileTree(): void {
    const repository = this.store.selectedRepository();
    const branch = this.store.selectedBranch();
    if (!repository || !branch) return;
    this.workspaceService.getFiles(repository.id, branch.name).subscribe((nodes) => this.store.fileTree.set(nodes));
  }

  private startOrResumeSession(): void {
    const repository = this.store.selectedRepository();
    const branch = this.store.selectedBranch();
    if (!repository || !branch) return;

    this.sessionService.createSession(repository.id, branch.name).subscribe((session) => {
      this.store.session.set(session);
      this.store.messages.set([]);
      this.store.fileChanges.set([]);
      this.store.execution.set(null);
      this.loadHistory();
      this.loadContext();
    });
  }

  private loadHistory(): void {
    const repository = this.store.selectedRepository();
    if (!repository) return;
    this.sessionService.listSessions(repository.id).subscribe((sessions) => this.store.sessions.set(sessions));
  }

  private loadContext(): void {
    const session = this.store.session();
    if (!session) return;
    this.contextBuilderService.getContextSummary(session.id).subscribe({
      next: (summary) => this.store.contextSummary.set(summary),
      error: () => this.store.contextSummary.set(null),
    });
  }

  addContextFile(filePath: string): void {
    const session = this.store.session();
    if (!session) return;
    const existing = this.store.contextSummary()?.files.map((file) => file.path) ?? [];
    if (existing.includes(filePath)) return;
    this.contextBuilderService
      .setPriorityFiles(session.id, [...existing, filePath])
      .subscribe((summary) => this.store.contextSummary.set(summary));
  }

  removeContextFile(filePath: string): void {
    const session = this.store.session();
    if (!session) return;
    const nextFiles = (this.store.contextSummary()?.files ?? [])
      .map((file) => file.path)
      .filter((path) => path !== filePath);
    this.contextBuilderService
      .setPriorityFiles(session.id, nextFiles)
      .subscribe((summary) => this.store.contextSummary.set(summary));
  }

  resumeSession(sessionId: string): void {
    this.sessionService.getSession(sessionId).subscribe((session) => {
      this.store.session.set(session);
      this.store.mode.set(session.mode);
      this.conversationService.getMessages(session.id).subscribe((messages) => this.store.messages.set(messages));
    });
  }

  setMode(mode: AiWorkspaceMode): void {
    this.store.mode.set(mode);
  }

  submitPrompt(prompt: string): void {
    const session = this.store.session();
    const repository = this.store.selectedRepository();
    const branch = this.store.selectedBranch();
    if (!prompt.trim() || !session || !repository || !branch || this.store.isRunning()) return;

    this.store.messages.update((messages) => [
      ...messages,
      {
        id: `local-${Date.now()}`,
        sessionId: session.id,
        role: 'user' as const,
        content: prompt,
        createdAt: new Date().toISOString(),
      },
    ]);
    this.store.isRunning.set(true);

    const payload = { sessionId: session.id, repositoryId: repository.id, branch: branch.name, prompt };

    if (this.store.mode() === 'ask') {
      this.aiWorkspaceService.ask(payload).subscribe({
        next: (message) => {
          this.store.messages.update((messages) => [...messages, message]);
          this.store.isRunning.set(false);
        },
        error: () => this.store.isRunning.set(false),
      });
    } else {
      this.agentService.startRun(payload).subscribe({
        next: (run) => {
          this.store.execution.set(run);
          this.store.fileChanges.set(run.filesChanged);
          this.store.messages.update((messages) => [
            ...messages,
            {
              id: `run-${run.id}`,
              sessionId: session.id,
              role: 'assistant' as const,
              content: `Proposed ${run.filesChanged.length} file change(s).`,
              createdAt: new Date().toISOString(),
              executionId: run.id,
            },
          ]);
          this.store.isRunning.set(false);

          this.agentService.getPlan(run.id).subscribe({
            next: (plan) => this.store.agentPlan.set(plan),
            error: () => this.store.agentPlan.set(null),
          });
        },
        error: () => this.store.isRunning.set(false),
      });
    }
  }

  /**
   * Manual path entry (WorkspaceSelectorComponent), as an alternative to picking a repository
   * from the dropdown list. Does not yet feed back into repository/branch selection or session
   * creation. V1 is path-first: a validated path is promoted into the repository selector.
   */
  validateWorkspacePath(path: string): void {
    this.workspaceService.validatePath(path).subscribe((workspace) => {
      this.store.workspace.set(workspace);
      if (!workspace.repository) return;

      const repository = {
        id: workspace.repository.id,
        name: workspace.repository.name,
        path: workspace.repository.path,
      };
      this.store.repositories.update((repositories) => {
        const existing = repositories.filter((item) => item.id !== repository.id);
        return [repository, ...existing];
      });
      this.selectRepository(repository);
    });
  }

  selectFileChange(fileChangeId: string): void {
    this.store.selectedFileChangeId.set(fileChangeId);
  }

  setFileDecision(fileChangeId: string, decision: 'kept' | 'rejected'): void {
    this.store.fileChanges.update((files) =>
      files.map((f) => (f.id === fileChangeId ? { ...f, decision } : f)),
    );
  }

  applyChanges(applyAll = false): void {
    const run = this.store.execution();
    if (!run) return;

    const keptFileIds = applyAll
      ? this.store.fileChanges().map((f) => f.id)
      : this.store.fileChanges().filter((f) => f.decision === 'kept').map((f) => f.id);
    if (!keptFileIds.length) return;

    this.reviewService.applyChanges({ runId: run.id, keptFileIds }).subscribe(() => {
      this.store.fileChanges.set([]);
      this.store.execution.set(null);
    });
  }

  loadPrompts(): void {
    this.promptLibraryService.listPrompts(this.store.mode()).subscribe((prompts) => this.store.prompts.set(prompts));
  }

  toggleSettings(): void {
    this.store.showSettings.update((value) => !value);
  }

  saveSettings(selectedModelId: string, enabledToolIds: string[], preferences: UserPreferences): void {
    this.modelRegistryService.updateRuntimeConfig({ selectedModelId }).subscribe((runtime) => {
      const registry = this.store.bootstrap()?.models;
      if (registry) this.store.bootstrap.update((b) => (b ? { ...b, models: { ...registry, runtime } } : b));
    });
    this.toolRegistryService.updateRuntimeSelection({ enabledToolIds }).subscribe((runtime) => {
      const registry = this.store.bootstrap()?.tools;
      if (registry) this.store.bootstrap.update((b) => (b ? { ...b, tools: { ...registry, runtime } } : b));
    });
    this.settingsService.updatePreferences(preferences).subscribe((updated) => {
      this.store.bootstrap.update((b) => (b ? { ...b, preferences: updated } : b));
    });
  }
}
