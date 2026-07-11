import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { BadgeModule } from 'primeng/badge';

export interface CurrentUser {
  initials: string;
  name: string;
  role: string;
}

@Component({
  selector: 'app-topbar',
  standalone: true,
  imports: [CommonModule, ButtonModule, BadgeModule],
  templateUrl: './topbar.component.html',
  styleUrl: './topbar.component.scss',
})
export class TopbarComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() notificationCount = 0;
  @Input() user: CurrentUser | null = null;
}
