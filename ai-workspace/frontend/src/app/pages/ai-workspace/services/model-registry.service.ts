import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { ModelRegistry, RuntimeConfiguration } from '../models/model-registry.model';

@Injectable({ providedIn: 'root' })
export class ModelRegistryService {
  constructor(private readonly http: HttpClient) {}

  getRegistry(): Observable<ModelRegistry> {
    return this.http.get<ModelRegistry>(`${AI_WORKSPACE_API_PREFIX}/models`);
  }

  updateRuntimeConfig(config: Partial<RuntimeConfiguration>): Observable<RuntimeConfiguration> {
    return this.http.put<RuntimeConfiguration>(`${AI_WORKSPACE_API_PREFIX}/models/runtime`, config);
  }
}
