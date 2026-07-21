import { Injectable, signal } from '@angular/core';

/** Distinguishes browser-offline from SSE-disconnected from run-failed. */
@Injectable({ providedIn: 'root' })
export class ConnectivityService {
  readonly online = signal(navigator.onLine);

  constructor() {
    window.addEventListener('online', () => this.online.set(true));
    window.addEventListener('offline', () => this.online.set(false));
  }
}
