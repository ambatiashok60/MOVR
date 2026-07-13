import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize, switchMap } from 'rxjs';
import { ActionProposal, ApiService, Proposal, Workspace } from './api.service';

interface Message { role: 'user' | 'assistant'; text: string; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  workspacePath = '';
  workspace?: Workspace;
  files: string[] = [];
  selected = new Set<string>();
  prompt = '';
  busy = false;
  error = '';
  reviewOpen = false;
  proposal?: Proposal;
  accepted = new Set<string>();
  activeDiff = 0;
  toolEvents: { tool: string; status: string }[] = [];
  actions: ActionProposal[] = [];
  messages: Message[] = [{
    role: 'assistant',
    text: 'Connect a local workspace, choose the context I should use, and tell me what you want to build.',
  }];

  constructor(private api: ApiService) {}

  connect(): void {
    if (!this.workspacePath.trim()) return;
    this.busy = true;
    this.error = '';
    this.api.validate(this.workspacePath.trim()).pipe(
      switchMap(workspace => {
        this.workspace = workspace;
        return this.api.files(workspace.path);
      }),
      finalize(() => this.busy = false),
    ).subscribe({
      next: result => this.files = result.files,
      error: error => this.error = error.error?.detail ?? 'Could not open this workspace.',
    });
  }

  toggle(file: string): void {
    this.selected.has(file) ? this.selected.delete(file) : this.selected.add(file);
  }

  send(): void {
    const text = this.prompt.trim();
    if (!text || !this.workspace || this.busy) return;
    this.messages.push({ role: 'user', text });
    this.prompt = '';
    this.busy = true;
    this.error = '';
    this.api.chat(this.workspace.path, text, [...this.selected]).pipe(
      finalize(() => this.busy = false),
    ).subscribe({
      next: response => {
        this.messages.push({ role: 'assistant', text: response.message });
        this.toolEvents = response.events;
        this.actions = response.actions;
        this.proposal = response.proposal ?? undefined;
        this.accepted = new Set(response.proposal?.changes.map(change => change.path) ?? []);
        this.activeDiff = 0;
      },
      error: error => this.error = error.error?.detail ?? 'The agent could not complete that request.',
    });
  }

  toggleChange(path: string): void {
    this.accepted.has(path) ? this.accepted.delete(path) : this.accepted.add(path);
  }

  applyChanges(): void {
    if (!this.proposal || !this.accepted.size || this.busy) return;
    this.busy = true;
    this.api.apply(this.proposal.id, [...this.accepted]).pipe(
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
}
