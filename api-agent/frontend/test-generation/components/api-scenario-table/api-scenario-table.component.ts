import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiScenarioTableRow } from '../../models/api-scenario-table.model';

@Component({
  selector: 'app-api-scenario-table',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './api-scenario-table.component.html',
  styleUrl: './api-scenario-table.component.scss',
})
export class ApiScenarioTableComponent {
  @Input() scenarios: ApiScenarioTableRow[] = [];
  @Input() selectedIds: string[] = [];
  @Input() selectedScenarioId: string | null = null;
  @Input() loading = false;
  @Input() generatingCodeForId: string | null = null;

  @Output() selectionChange = new EventEmitter<string[]>();
  @Output() generateCode = new EventEmitter<ApiScenarioTableRow>();
  @Output() openScenario = new EventEmitter<ApiScenarioTableRow>();
  @Output() editScenario = new EventEmitter<ApiScenarioTableRow>();
  @Output() deleteScenario = new EventEmitter<ApiScenarioTableRow>();

  isSelected(id: string): boolean {
    return this.selectedIds.includes(id);
  }

  toggle(id: string): void {
    const ids = this.isSelected(id)
      ? this.selectedIds.filter((selectedId) => selectedId !== id)
      : [...this.selectedIds, id];
    this.selectionChange.emit(ids);
  }

  toggleAll(): void {
    this.selectionChange.emit(this.selectedIds.length === this.scenarios.length ? [] : this.scenarios.map((row) => row.id));
  }

  trackById(_: number, row: ApiScenarioTableRow): string {
    return row.id;
  }
}
