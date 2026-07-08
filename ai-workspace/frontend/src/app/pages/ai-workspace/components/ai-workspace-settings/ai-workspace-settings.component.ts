import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { CheckboxModule } from 'primeng/checkbox';
import { DropdownModule } from 'primeng/dropdown';

import { ModelRegistry } from '../../models/model-registry.model';
import { ToolRegistry } from '../../models/tool-registry.model';
import { UserPreferences } from '../../models/bootstrap.model';

export interface SettingsSaveEvent {
  selectedModelId: string;
  enabledToolIds: string[];
  preferences: UserPreferences;
}

@Component({
  selector: 'app-ai-workspace-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, CheckboxModule, DropdownModule],
  templateUrl: './ai-workspace-settings.component.html',
  styleUrl: './ai-workspace-settings.component.scss',
})
export class AiWorkspaceSettingsComponent {
  @Input() modelRegistry: ModelRegistry | null = null;
  @Input() toolRegistry: ToolRegistry | null = null;
  @Input() preferences: UserPreferences | null = null;
  @Output() save = new EventEmitter<SettingsSaveEvent>();

  selectedModelId = '';
  enabledToolIds: string[] = [];

  ngOnChanges(): void {
    this.selectedModelId = this.modelRegistry?.runtime.selectedModelId ?? '';
    this.enabledToolIds = [...(this.toolRegistry?.runtime.enabledToolIds ?? [])];
  }

  toggleTool(toolId: string, checked: boolean): void {
    this.enabledToolIds = checked
      ? [...this.enabledToolIds, toolId]
      : this.enabledToolIds.filter((id) => id !== toolId);
  }

  submit(): void {
    if (!this.preferences) return;
    this.save.emit({
      selectedModelId: this.selectedModelId,
      enabledToolIds: this.enabledToolIds,
      preferences: this.preferences,
    });
  }
}
