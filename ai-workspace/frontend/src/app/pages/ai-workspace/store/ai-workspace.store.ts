import { Injectable, signal } from '@angular/core';

import { AiWorkspaceMode } from '../models/ai-workspace.model';
import { BootstrapPayload } from '../models/bootstrap.model';
import { ChatMessage } from '../models/chat-message.model';
import { ContextSummary } from '../models/context.model';
import { ExecutionRun } from '../models/execution.model';
import { FileChange } from '../models/file-change.model';
import { AgentPlan } from '../models/agent-plan.model';
import { PromptTemplate } from '../models/prompt.model';
import { AiSession } from '../models/session.model';
import { AiFileNode, WorkspaceInfo } from '../models/workspace.model';
import { BranchOption, RepositoryOption } from '../services/workspace.service';

/**
 * Plain signal-based state container. No behavior here — services call in, the facade
 * orchestrates, components only ever read this store's signals or call the facade.
 */
@Injectable({ providedIn: 'root' })
export class AiWorkspaceStore {
  readonly bootstrap = signal<BootstrapPayload | null>(null);

  readonly workspace = signal<WorkspaceInfo | null>(null);
  readonly repositories = signal<RepositoryOption[]>([]);
  readonly branches = signal<BranchOption[]>([]);
  readonly selectedRepository = signal<RepositoryOption | null>(null);
  readonly selectedBranch = signal<BranchOption | null>(null);
  readonly fileTree = signal<AiFileNode[]>([]);

  readonly session = signal<AiSession | null>(null);
  readonly sessions = signal<AiSession[]>([]);
  readonly mode = signal<AiWorkspaceMode>('agent');

  readonly messages = signal<ChatMessage[]>([]);
  readonly contextSummary = signal<ContextSummary | null>(null);

  readonly execution = signal<ExecutionRun | null>(null);
  readonly agentPlan = signal<AgentPlan | null>(null);
  readonly isRunning = signal(false);

  /** File changes proposed by the most recent Agent run, with live keep/reject decisions. */
  readonly fileChanges = signal<FileChange[]>([]);
  readonly selectedFileChangeId = signal<string | null>(null);

  readonly prompts = signal<PromptTemplate[]>([]);
  readonly showSettings = signal(false);
}
