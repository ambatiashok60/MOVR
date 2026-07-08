import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

export interface NavItem {
  label: string;
  icon: string;
  routerLink: string;
  badge?: string;
}

// TODO integration: replace with the host app's real nav config (app-constants.ts or similar)
// once available — this list is reconstructed from the approved AI Workspace mockup.
const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: 'pi pi-home', routerLink: '/dashboard' },
  { label: 'Projects', icon: 'pi pi-folder', routerLink: '/projects' },
  { label: 'Data Sources', icon: 'pi pi-database', routerLink: '/data-sources' },
  { label: 'Prompt Management', icon: 'pi pi-file-edit', routerLink: '/prompt-management' },
  { label: 'Coverage', icon: 'pi pi-chart-bar', routerLink: '/coverage' },
  { label: 'Review Management', icon: 'pi pi-verified', routerLink: '/review-management' },
  { label: 'AI Workspace', icon: 'pi pi-sparkles', routerLink: '/ai-workspace', badge: 'BETA' },
];

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent {
  readonly navItems = NAV_ITEMS;
}
