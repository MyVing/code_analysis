const API_BASE = '/api/v1';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers: customHeaders, ...rest } = options || {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: { 'Content-Type': 'application/json', ...customHeaders },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

import type { Project, Symbol, CallGraphEdge, GraphData, ImportRecord } from '@/types';

export const api = {
  // Projects
  listProjects: () => request<Project[]>('/projects/'),
  createProject: (data: { name: string; git_url: string; language?: string; branch?: string }) =>
    request<Project>('/projects/', { method: 'POST', body: JSON.stringify(data) }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  listProjectFiles: (id: string) => request<any[]>(`/projects/${id}/files`),

  // Symbols
  querySymbols: (params?: { name?: string; kind?: string; file_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.name) qs.set('name', params.name);
    if (params?.kind) qs.set('kind', params.kind);
    if (params?.file_id) qs.set('file_id', params.file_id);
    const query = qs.toString();
    return request<Symbol[]>(`/symbols/${query ? `?${query}` : ''}`);
  },
  getFileSymbols: (fileId: string) => request<Symbol[]>(`/symbols/file/${fileId}`),
  getSymbolChildren: (symbolId: string) => request<Symbol[]>(`/symbols/${symbolId}/children`),

  // Graph
  getCallGraph: (projectId: string) => request<CallGraphEdge[]>(`/graph/call-graph/${projectId}`),
  getImports: (projectId: string) => request<ImportRecord[]>(`/graph/imports/${projectId}`),
  getVisualization: (projectId: string) => request<GraphData>(`/graph/visualization/${projectId}`),
  expandSymbol: (projectId: string, symbolId: string) =>
    request<any>(`/graph/call-graph/${projectId}/expand/${symbolId}`),
  getFileSymbols: (projectId: string, fileId: string) =>
    request<GraphData>(`/graph/file-symbols/${projectId}/${fileId}`),
  expandCall: (projectId: string, symbolId: string) =>
    request<any>(`/graph/expand-call/${projectId}/${symbolId}`),
  expandClassCalls: (projectId: string, symbolId: string) =>
    request<any>(`/graph/expand-class-calls/${projectId}/${symbolId}`),
  getFullChain: (projectId: string, symbolId: string) =>
    request<GraphData>(`/graph/full-chain/${projectId}/${symbolId}`),

  // Files
  getFileContent: (fileId: string) => request<{ id: string; file_path: string; language: string; content: string }>(`/files/${fileId}/content`),

  // Chat
  chatStream: (projectId: string, message: string, sessionId?: string) => {
    const body: any = { message };
    if (sessionId) body.session_id = sessionId;
    return fetch(`${API_BASE}/chat/${projectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  },

  // Health
  healthCheck: () => request<{ status: string; version: string }>('/health'),
};
