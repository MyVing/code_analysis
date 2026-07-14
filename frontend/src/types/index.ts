import type { Node, Edge } from '@xyflow/react';

export type SymbolKind = 'class' | 'method' | 'function' | 'variable' | 'interface' | 'annotation' | 'enum';

export type ProjectStatus = 'pending' | 'cloning' | 'parsing' | 'indexing' | 'ready' | 'error';

export interface Project {
  id: string;
  name: string;
  git_url: string;
  language: string;
  framework: string | null;
  branch: string;
  commit: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface Symbol {
  id: string;
  file_id: string;
  parent_id: string | null;
  name: string;
  kind: SymbolKind;
  signature: string | null;
  start_line: number;
  end_line: number;
  modifiers: string | null;
}

export interface CallGraphEdge {
  id: string;
  caller_id: string;
  callee_id: string;
  file_id: string;
  line_number: number;
}

export interface ImportRecord {
  id: string;
  source_file_id: string;
  target_module: string;
  import_type: 'import' | 'from_import' | 'static_import';
}

// React Flow custom types
export type NodeType = 'classNode' | 'methodNode' | 'fieldNode' | 'fileNode' | 'externalNode';

export type EdgeType = 'call' | 'inherit' | 'import' | 'implement' | 'contains' | 'field_access';

// Layer base hues based on file path patterns (HSL hue values)
function getLayerHue(filePath: string): number | null {
  const lower = filePath.toLowerCase();
  if (lower.includes('controller')) return 220;       // blue
  if (lower.includes('service')) return 160;           // green
  if (lower.includes('mapper') || lower.includes('dao') || lower.includes('repository')) return 40; // orange
  if (lower.includes('dto') || lower.includes('entity') || lower.includes('model') || lower.includes('vo')) return 270; // purple
  if (lower.includes('config') || lower.includes('configuration')) return 330; // pink
  return null;
}

// Color by combining layer (file path) + node kind for clear visual distinction
export function getLayerColor(filePath: string, kind: SymbolKind): string {
  const layerHue = getLayerHue(filePath);

  if (layerHue !== null) {
    // Same layer hue, but different saturation/lightness per kind
    if (kind === 'class' || kind === 'interface' || kind === 'enum') {
      return `hsl(${layerHue}, 65%, 42%)`;   // deep & saturated — class stands out
    }
    if (kind === 'method' || kind === 'function') {
      return `hsl(${layerHue}, 50%, 55%)`;   // medium — method is lighter
    }
    if (kind === 'variable') {
      return `hsl(${layerHue}, 35%, 65%)`;   // pale — field is subtle
    }
    if (kind === 'annotation') {
      return `hsl(${layerHue}, 70%, 50%)`;
    }
    return `hsl(${layerHue}, 45%, 50%)`;
  }

  // No layer match — use kind-based defaults with distinct hues
  if (kind === 'class' || kind === 'interface' || kind === 'enum') return '#4f46e5'; // indigo
  if (kind === 'method' || kind === 'function') return '#0891b2';                    // cyan
  if (kind === 'variable') return '#d97706';                                          // amber
  return '#6b7280';
}

export interface CustomNodeData {
  label: string;
  type: NodeType;
  filePath: string;
  startLine: number;
  endLine: number;
  kind: SymbolKind;
  color?: string;
  methodCount?: number;
  parentId?: string;
  fileId?: string;
  signature?: string;
  modifiers?: string;
  hasOutgoingCalls?: boolean;
  isExpanded?: boolean;
}

export type CustomNode = Node<CustomNodeData>;

export interface CustomEdgeData {
  label?: string;
  type: EdgeType;
  lineNumber?: number;
}

export type CustomEdge = Edge<CustomEdgeData>;

export interface GraphData {
  nodes: GraphNodeApi[];
  edges: GraphEdgeApi[];
}

export interface GraphNodeApi {
  id: string;
  name: string;
  kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  parent_id?: string | null;
  file_id?: string | null;
  signature?: string | null;
  modifiers?: string | null;
}

export interface GraphEdgeApi {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  line_number: number | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'thinking';
  content: string;
  timestamp: number;
  toolName?: string;
  toolArgs?: Record<string, any>;
  isStreaming?: boolean;
  toolSteps?: { tool: string; args?: Record<string, any> }[];
}
