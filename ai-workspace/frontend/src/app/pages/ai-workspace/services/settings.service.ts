import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { UserPreferences } from '../models/bootstrap.model';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  constructor(private readonly http: HttpClient) {}

  getPreferences(): Observable<UserPreferences> {
    return this.http.get<UserPreferences>(`${AI_WORKSPACE_API_PREFIX}/settings/preferences`);
  }

  updatePreferences(preferences: Partial<UserPreferences>): Observable<UserPreferences> {
    return this.http.put<UserPreferences>(`${AI_WORKSPACE_API_PREFIX}/settings/preferences`, preferences);
  }
}
