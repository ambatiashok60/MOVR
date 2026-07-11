import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { BootstrapPayload } from '../models/bootstrap.model';

@Injectable({ providedIn: 'root' })
export class BootstrapService {
  constructor(private readonly http: HttpClient) {}

  getBootstrap(): Observable<BootstrapPayload> {
    return this.http.get<BootstrapPayload>(`${AI_WORKSPACE_API_PREFIX}/bootstrap`);
  }
}
