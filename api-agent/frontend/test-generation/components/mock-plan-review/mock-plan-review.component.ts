import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { MockStubPlan } from '../../models/api-test-generation.model';

@Component({
  selector: 'app-mock-plan-review',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mock-plan-review.component.html',
  styleUrl: './mock-plan-review.component.scss',
})
export class MockPlanReviewComponent {
  @Input({ required: true }) plan!: MockStubPlan;
  @Input() approving = false;
  @Output() approve = new EventEmitter<void>();
}
