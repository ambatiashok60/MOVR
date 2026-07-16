import { CommonModule } from '@angular/common';
import { Component, ElementRef, HostListener, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize, Subscription, switchMap } from 'rxjs';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { ActionProposal, ApiService, Proposal, RuntimeConfig, Session, Workspace } from './api.service';

interface Message { role: 'user' | 'assistant'; text: string; html?: string; contextFiles?: string[]; }
interface TreeNode { name: string; path: string; directory: boolean; depth: number; expanded: boolean; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  workspacePath = '';
  workspace?: Workspace;
  files: string[] = [];
  tree: TreeNode[] = [];
  fileQuery = '';
  selected = new Set<string>();
  prompt = '';
  busy = false;
  workspaceStatus: 'disconnected' | 'validating' | 'loading' | 'connected' | 'error' = 'disconnected';
  chatSubscription?: Subscription;
  failedPrompt = '';
  error = '';
  reviewOpen = false;
  proposal?: Proposal;
  accepted = new Set<string>();
  acceptedHunks: Record<string, Set<string>> = {};
  activeDiff = 0;
  toolEvents: { tool: string; status: string }[] = [];
  actions: ActionProposal[] = [];
  plan: { step: string; status: string }[] = [];
  relationships: { path: string; line: number; text: string; relation: string }[] = [];
  runtime?: RuntimeConfig;
  responseDetail: 'auto' | 'brief' | 'detailed' = 'auto';
  agentMode: 'debug' | 'analyze' | 'migrate' | 'refactor' | 'tests' = 'debug';
  sessions: Session[] = [];
  sessionsOpen = false;
  session?: Session;
  sidebarWidth = Number(localStorage.getItem('arc.sidebarWidth') || 270);
  resizingSidebar = false;
  @ViewChild('messageScroll') messageScroll?: ElementRef<HTMLElement>;
  messages: Message[] = [{
    role: 'assistant',
    text: 'Connect a local workspace, choose the context I should use, and tell me what you want to build.',
  }];

  constructor(private api: ApiService) {}

  newSession(): void {
    this.stop();
    this.messages = [{ role: 'assistant', text: 'New session started. What would you like to work on?' }];
    this.prompt = '';
    this.selected.clear();
    this.proposal = undefined;
    this.accepted.clear();
    this.actions = [];
    this.plan = [];
    this.relationships = [];
    this.toolEvents = [];
    this.error = '';
    this.failedPrompt = '';
    if (this.workspace) this.api.createSession(this.workspace.path).subscribe(session => this.session = session);
  }

  @HostListener('document:pointermove', ['$event']) resizeSidebar(event: PointerEvent): void {
    if (!this.resizingSidebar) return;
    this.sidebarWidth = Math.max(220, Math.min(460, event.clientX));
  }

  @HostListener('document:pointerup') stopResizeSidebar(): void {
    if (this.resizingSidebar) localStorage.setItem('arc.sidebarWidth', String(this.sidebarWidth));
    this.resizingSidebar = false;
  }

  startResizeSidebar(event: PointerEvent): void { event.preventDefault(); this.resizingSidebar = true; }

  ngOnInit(): void {
    this.api.runtimeConfig().subscribe({ next: config => this.runtime = config });
  }

  connect(): void {
    if (!this.workspacePath.trim()) return;
    this.busy = true;
    this.workspaceStatus = 'validating';
    this.error = '';
    this.api.validate(this.workspacePath.trim()).pipe(
      switchMap(workspace => {
        this.workspace = workspace;
        this.workspaceStatus = 'loading';
        return this.api.files(workspace.path);
      }),
      finalize(() => this.busy = false),
    ).subscribe({
      next: result => {
        this.files = result.files; this.tree = this.buildTree(result.files); this.workspaceStatus = 'connected';
        this.api.createSession(this.workspace?.path || this.workspacePath).subscribe(session => this.session = session);
        this.api.sessions().subscribe(value => this.sessions = value.sessions.filter(item => item.workspace === this.workspace?.path));
      },
      error: error => { this.workspaceStatus = 'error'; this.error = error.error?.detail ?? 'Could not open this workspace.'; },
    });
  }

  toggle(file: string): void {
    this.selected.has(file) ? this.selected.delete(file) : this.selected.add(file);
  }

  visibleTree(): TreeNode[] {
    const query = this.fileQuery.trim().toLowerCase();
    if (query) return this.tree.filter(node => node.path.toLowerCase().includes(query));
    return this.tree.filter(node => {
      const parts = node.path.split('/');
      return parts.slice(1, -1).every((_, index) => this.tree.find(folder => folder.path === parts.slice(0, index + 1).join('/'))?.expanded !== false);
    });
  }

  toggleFolder(node: TreeNode): void {
    if (node.directory) node.expanded = !node.expanded;
  }

  removeSelected(file: string): void { this.selected.delete(file); }

  handleComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  markdown(text: string): string {
    return DOMPurify.sanitize(marked.parse(text, { async: false }) as string);
  }

  diffLines(diff: string): { text: string; kind: 'add' | 'del' | 'hunk' | 'meta' | 'ctx' }[] {
    return diff.split('\n').map(line => ({
      text: line,
      kind: line.startsWith('@@') ? 'hunk'
        : line.startsWith('+++') || line.startsWith('---') ? 'meta'
        : line.startsWith('+') ? 'add'
        : line.startsWith('-') ? 'del'
        : 'ctx',
    }));
  }

  planProgress(): string {
    const done = this.plan.filter(step => step.status === 'completed').length;
    return `${done}/${this.plan.length}`;
  }

  private buildTree(paths: string[]): TreeNode[] {
    const result: TreeNode[] = [];
    const folders = new Set<string>();
    for (const path of paths) {
      const parts = path.split('/');
      for (let i = 1; i < parts.length; i++) folders.add(parts.slice(0, i).join('/'));
    }
    for (const path of [...folders, ...paths].sort()) {
      const parts = path.split('/');
      result.push({ name: parts.at(-1) || path, path, directory: folders.has(path), depth: parts.length - 1, expanded: true });
    }
    return result;
  }

  send(): void {
    const text = this.prompt.trim();
    if (!text || !this.workspace || this.busy) return;
    const scopedPrompt = `[Mode: ${this.agentMode}]\n${text}`;
    this.messages.push({ role: 'user', text, contextFiles: [...this.selected] });
    this.prompt = '';
    this.busy = true;
    this.error = '';
    this.failedPrompt = '';
    this.chatSubscription = this.api.chat(this.workspace.path, scopedPrompt, [...this.selected], this.responseDetail, this.session?.id).pipe(
      finalize(() => this.busy = false),
    ).subscribe({
      next: response => {
        this.messages.push({ role: 'assistant', text: response.message, html: this.markdown(response.message) });
        setTimeout(() => { const element = this.messageScroll?.nativeElement; if (element) element.scrollTop = element.scrollHeight; });
        this.toolEvents = response.events;
        this.plan = response.plan;
        this.relationships = response.relationships ?? [];
        this.actions = response.actions;
        this.proposal = response.proposal ?? undefined;
        this.accepted = new Set(response.proposal?.changes.map(change => change.path) ?? []);
        this.acceptedHunks = {};
        response.proposal?.changes.forEach(change => this.acceptedHunks[change.path] = new Set((change.hunks ?? []).map(hunk => hunk.id)));
        this.activeDiff = 0;
      },
      error: error => { this.failedPrompt = text; this.prompt = text; this.error = error.error?.detail ?? 'The agent could not complete that request.'; },
    });
  }

  toggleChange(path: string): void {
    this.accepted.has(path) ? this.accepted.delete(path) : this.accepted.add(path);
  }

  toggleHunk(path: string, id: string): void {
    const set = this.acceptedHunks[path] ?? new Set<string>();
    set.has(id) ? set.delete(id) : set.add(id);
    this.acceptedHunks[path] = set;
  }

  applyChanges(): void {
    if (!this.proposal || !this.accepted.size || this.busy) return;
    this.busy = true;
    const hunks: Record<string, string[]> = {};
    Object.entries(this.acceptedHunks).forEach(([path, ids]) => hunks[path] = [...ids]);
    this.api.apply(this.proposal.id, [...this.accepted], hunks).pipe(
      finalize(() => this.busy = false),
    ).subscribe({
      next: result => {
        this.messages.push({ role: 'assistant', text: `Applied ${result.applied.length} approved file change(s).` });
        this.proposal = undefined;
        this.accepted.clear();
        if (this.workspace) this.api.files(this.workspace.path).subscribe(value => this.files = value.files);
      },
      error: error => this.error = error.error?.detail ?? 'Could not apply the approved changes.',
    });
  }

  approveAction(action: ActionProposal): void {
    if (this.busy) return;
    this.busy = true;
    this.api.approveAction(action.id).pipe(finalize(() => this.busy = false)).subscribe({
      next: result => {
        this.actions = this.actions.filter(item => item.id !== action.id);
        if (result.proposal) {
          this.proposal = result.proposal;
          this.accepted = new Set(result.proposal.changes.map(change => change.path));
          this.acceptedHunks = {};
          result.proposal.changes.forEach(change => this.acceptedHunks[change.path] = new Set((change.hunks ?? []).map(hunk => hunk.id)));
          this.activeDiff = 0;
        }
        if (result.installed) {
          this.messages.push({ role: 'assistant', text: `Installed the reviewed tool “${result.installed}”. It is available to future agent runs.` });
        }
      },
      error: error => this.error = error.error?.detail ?? 'The proposed tool could not be approved.',
    });
  }

  rejectAction(action: ActionProposal): void {
    this.actions = this.actions.filter(item => item.id !== action.id);
  }

  stop(): void { this.chatSubscription?.unsubscribe(); this.busy = false; }
  retry(): void { if (this.failedPrompt) this.send(); }

  toggleSessions(): void {
    this.sessionsOpen = !this.sessionsOpen;
    if (this.sessionsOpen) this.api.sessions().subscribe(value => this.sessions = value.sessions);
  }

  reopenSession(session: Session): void {
    this.stop(); this.session = session; this.sessionsOpen = false;
    this.api.sessionMessages(session.id).subscribe(result => {
      this.messages = [{ role: 'assistant', text: `Session restored · ${new Date(session.updatedAt).toLocaleString()}` }];
      for (const item of result.messages) {
        const role = item.role === 'user' ? 'user' : 'assistant';
        const text = item.content || item.text || '';
        this.messages.push({ role, text, html: role === 'assistant' ? this.markdown(text) : undefined, contextFiles: item.contextFiles });
      }
    });
  }
}
