import { Injectable, Signal, computed } from '@angular/core';

import { AiWorkspaceStore } from './ai-workspace.store';

/**
 * Computed, read-only views over AiWorkspaceStore. Kept separate from the store itself so
 * derived values (counts, "is anything selected") aren't recomputed ad hoc in components.
 */
@Injectable({ providedIn: 'root' })
export class AiWorkspaceSelectors {
  constructor(private readonly store: AiWorkspaceStore) {}

  readonly hasValidWorkspace: Signal<boolean> = computed(
    () => this.store.workspace()?.validationState === 'valid',
  );

  readonly canRunAgent: Signal<boolean> = computed(
    () => this.hasValidWorkspace() && !!this.store.selectedBranch() && !this.store.isRunning(),
  );

  readonly currentTask: Signal<string | undefined> = computed(() => this.store.session()?.currentTask);

  readonly keptCount: Signal<number> = computed(
    () => this.store.fileChanges().filter((f) => f.decision === 'kept').length,
  );

  readonly rejectedCount: Signal<number> = computed(
    () => this.store.fileChanges().filter((f) => f.decision === 'rejected').length,
  );

  readonly selectableFileCount: Signal<number> = computed(
    () => this.store.fileChanges().filter((f) => f.decision !== 'rejected').length,
  );

  readonly selectedFileChange = computed(() => {
    const id = this.store.selectedFileChangeId();
    if (!id) return null;
    return this.store.fileChanges().find((f) => f.id === id) ?? null;
  });
}
