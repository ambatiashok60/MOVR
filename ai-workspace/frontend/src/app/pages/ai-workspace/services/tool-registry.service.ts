import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { RuntimeToolSelection, ToolRegistry } from '../models/tool-registry.model';

@Injectable({ providedIn: 'root' })
export class ToolRegistryService {
  constructor(private readonly http: HttpClient) {}

  getRegistry(): Observable<ToolRegistry> {
    return this.http.get<ToolRegistry>(`${AI_WORKSPACE_API_PREFIX}/tools`);
  }

  updateRuntimeSelection(selection: RuntimeToolSelection): Observable<RuntimeToolSelection> {
    return this.http.put<RuntimeToolSelection>(`${AI_WORKSPACE_API_PREFIX}/tools/runtime`, selection);
  }
}
