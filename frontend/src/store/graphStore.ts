import { create } from 'zustand';
import type { CustomNode, CustomEdge, Symbol } from '@/types';
import { getLayerColor } from '@/types';
import { api } from '@/services/api';

function buildNode(n: any, overrides?: Partial<CustomNode['data']>): CustomNode {
  const isMethod = n.kind === 'method' || n.kind === 'function';
  const isField = n.kind === 'variable';
  const nodeType = isField ? 'fieldNode' : isMethod ? 'methodNode' : 'classNode';
  const color = getLayerColor(n.file_path || '', n.kind);

  return {
    id: String(n.id),
    type: nodeType,
    position: { x: 0, y: 0 },
    data: {
      label: n.name,
      type: nodeType as CustomNode['data']['type'],
      filePath: n.file_path,
      startLine: n.start_line,
      endLine: n.end_line,
      kind: n.kind as Symbol['kind'],
      color,
      parentId: n.parent_id ?? undefined,
      fileId: n.file_id ?? undefined,
      signature: n.signature ?? undefined,
      modifiers: n.modifiers ?? undefined,
      hasOutgoingCalls: false,
      isExpanded: false,
      ...overrides,
    },
  };
}

function buildEdge(e: any): CustomEdge {
  return {
    id: String(e.id),
    source: String(e.source),
    target: String(e.target),
    type: 'call',
    data: {
      type: (e.edge_type || 'call') as CustomEdge['data']['type'],
      lineNumber: e.line_number,
    },
  };
}

/** Merge new nodes/edges into existing, deduplicating by id */
function mergeGraph(
  existingNodes: CustomNode[],
  existingEdges: CustomEdge[],
  newNodes: CustomNode[],
  newEdges: CustomEdge[],
): { nodes: CustomNode[]; edges: CustomEdge[] } {
  const nodeMap = new Map(existingNodes.map((n) => [n.id, n]));
  for (const n of newNodes) {
    if (!nodeMap.has(n.id)) {
      nodeMap.set(n.id, n);
    }
  }
  const edgeMap = new Map(existingEdges.map((e) => [e.id, e]));
  for (const e of newEdges) {
    if (!edgeMap.has(e.id)) {
      edgeMap.set(e.id, e);
    }
  }
  return { nodes: Array.from(nodeMap.values()), edges: Array.from(edgeMap.values()) };
}

interface GraphStore {
  nodes: CustomNode[];
  edges: CustomEdge[];
  selectedNode: CustomNode | null;
  selectedSymbol: Symbol | null;
  expandedNodes: Set<string>;
  expandedCallNodes: Set<string>;
  chainFileId: string | null;
  involvedFileIds: Set<string>;
  focusNodeId: string | null;
  focusStack: string[];
  loading: boolean;

  loadGraph: (projectId: string) => Promise<void>;
  loadFileChain: (projectId: string, fileId: string) => Promise<void>;
  expandCall: (projectId: string, symbolId: string) => Promise<void>;
  expandClassCalls: (projectId: string, symbolId: string) => Promise<void>;
  loadFullChain: (projectId: string, symbolId: string) => Promise<void>;
  selectNode: (node: CustomNode | null) => void;
  expandNode: (projectId: string, nodeId: string) => Promise<void>;
  collapseNode: (nodeId: string) => void;
  collapseCallNode: (nodeId: string) => void;
  focusOnNode: (nodeId: string) => void;
  focusBack: () => void;
  clear: () => void;
}

export const useGraphStore = create<GraphStore>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  selectedSymbol: null,
  expandedNodes: new Set(),
  expandedCallNodes: new Set(),
  chainFileId: null,
  involvedFileIds: new Set(),
  focusNodeId: null,
  focusStack: [],
  loading: false,

  loadGraph: async (projectId) => {
    set({ loading: true });
    try {
      const data = await api.getVisualization(projectId);

      const parentCount: Record<string, number> = {};
      for (const n of data.nodes) {
        if (n.parent_id) {
          parentCount[n.parent_id] = (parentCount[n.parent_id] || 0) + 1;
        }
      }

      const nodes: CustomNode[] = data.nodes.map((n) => {
        const node = buildNode(n);
        node.data.methodCount = parentCount[n.id] || 0;
        return node;
      });

      const edges: CustomEdge[] = data.edges.map((e) => buildEdge(e));

      const callerIds = new Set(edges.map((e) => e.source));
      for (const node of nodes) {
        if (callerIds.has(node.id)) {
          node.data.hasOutgoingCalls = true;
        }
      }

      const involvedFileIds = new Set(
        nodes.map((n) => n.data.fileId).filter(Boolean) as string[],
      );

      set({ nodes, edges, loading: false, expandedNodes: new Set(), expandedCallNodes: new Set(), chainFileId: null, involvedFileIds });
    } catch {
      set({ loading: false });
    }
  },

  loadFileChain: async (projectId, fileId) => {
    set({ loading: true });
    try {
      // Step 1: Get file symbols (first layer)
      const fileData = await api.getFileSymbols(projectId, fileId);
      const initialNodes: CustomNode[] = fileData.nodes.map((n: any) => buildNode(n));
      const initialEdges: CustomEdge[] = fileData.edges.map((e: any) => buildEdge(e));

      // Find class nodes in this file — we'll load full chain for each
      const classNodes = initialNodes.filter(
        (n) => n.data.kind === 'class' || n.data.kind === 'interface',
      );

      if (classNodes.length === 0) {
        // No classes, just show the file symbols
        for (const node of initialNodes) {
          if (node.data.kind === 'method' || node.data.kind === 'function' || node.data.kind === 'class') {
            node.data.hasOutgoingCalls = true;
          }
        }
        const involvedFileIds = new Set(
          initialNodes.map((n) => n.data.fileId).filter(Boolean) as string[],
        );
        set({
          nodes: initialNodes,
          edges: initialEdges,
          loading: false,
          expandedNodes: new Set(),
          expandedCallNodes: new Set(),
          chainFileId: fileId,
          selectedNode: null,
          involvedFileIds,
        });
        return;
      }

      // Step 2: Load full chain for each class (all at once via full-chain API)
      let allNodes = initialNodes;
      let allEdges = initialEdges;

      for (const classNode of classNodes) {
        try {
          const chainData = await api.getFullChain(projectId, classNode.id);
          const chainNodes: CustomNode[] = chainData.nodes.map((n: any) => buildNode(n));
          const chainEdges: CustomEdge[] = chainData.edges.map((e: any) => buildEdge(e));

          const merged = mergeGraph(allNodes, allEdges, chainNodes, chainEdges);
          allNodes = merged.nodes;
          allEdges = merged.edges;
        } catch {
          // Skip if full chain fails for this class
        }
      }

      // Mark nodes that have outgoing calls
      const callerIds = new Set(
        allEdges.filter((e) => e.data.type === 'call').map((e) => e.source),
      );
      const expandedSet = new Set<string>();

      for (const node of allNodes) {
        const hasCalls = callerIds.has(node.id);
        node.data.hasOutgoingCalls = hasCalls;
        node.data.isExpanded = hasCalls;
        if (hasCalls) {
          expandedSet.add(node.id);
        }
      }

      const involvedFileIds = new Set(
        allNodes.map((n) => n.data.fileId).filter(Boolean) as string[],
      );

      set({
        nodes: allNodes,
        edges: allEdges,
        loading: false,
        expandedNodes: new Set(),
        expandedCallNodes: expandedSet,
        chainFileId: fileId,
        selectedNode: null,
        involvedFileIds,
      });
    } catch {
      set({ loading: false });
    }
  },

  expandCall: async (projectId, symbolId) => {
    const { expandedCallNodes, nodes, edges } = get();
    const sid = String(symbolId);
    if (expandedCallNodes.has(sid)) return;

    try {
      const data = await api.expandCall(projectId, symbolId);

      const newNodes: CustomNode[] = data.child_nodes.map((n: any) => buildNode(n));
      const newEdges: CustomEdge[] = data.edges.map((e: any) => buildEdge(e));

      // Deduplicate: only add nodes not already in graph
      const existingIds = new Set(nodes.map((n) => n.id));
      const uniqueNewNodes = newNodes.filter((n) => !existingIds.has(n.id));

      // Only keep edges whose source and target exist in the combined graph
      const allNodeIds = new Set([...nodes.map((n) => n.id), ...newNodes.map((n) => n.id)]);
      const validNewEdges = newEdges.filter(
        (e) => allNodeIds.has(e.source) && allNodeIds.has(e.target),
      );

      // Deduplicate edges
      const existingEdgeIds = new Set(edges.map((e) => e.id));
      const uniqueNewEdges = validNewEdges.filter((e) => !existingEdgeIds.has(e.id));

      for (const node of uniqueNewNodes) {
        if (node.data.kind === 'method' || node.data.kind === 'function' || node.data.kind === 'class') {
          node.data.hasOutgoingCalls = true;
        }
      }

      // Mark the expanded node
      const updatedNodes = nodes.map((n) =>
        n.id === sid ? { ...n, data: { ...n.data, isExpanded: true } } : n,
      );

      const nextExpanded = new Set(expandedCallNodes);
      nextExpanded.add(sid);

      const involvedFileIds = new Set(get().involvedFileIds);
      for (const n of uniqueNewNodes) {
        if (n.data.fileId) involvedFileIds.add(n.data.fileId);
      }

      set({
        nodes: [...updatedNodes, ...uniqueNewNodes],
        edges: [...edges, ...uniqueNewEdges],
        expandedCallNodes: nextExpanded,
        involvedFileIds,
      });
    } catch {
      // silently fail
    }
  },

  expandClassCalls: async (projectId, symbolId) => {
    const { expandedCallNodes, nodes, edges } = get();
    const sid = String(symbolId);
    if (expandedCallNodes.has(sid)) return;

    try {
      const data = await api.expandClassCalls(projectId, symbolId);

      const newNodes: CustomNode[] = data.child_nodes.map((n: any) => buildNode(n));
      const newEdges: CustomEdge[] = data.edges.map((e: any) => buildEdge(e));

      const existingIds = new Set(nodes.map((n) => n.id));
      const uniqueNewNodes = newNodes.filter((n) => !existingIds.has(n.id));

      const allNodeIds = new Set([...nodes.map((n) => n.id), ...newNodes.map((n) => n.id)]);
      const validNewEdges = newEdges.filter(
        (e) => allNodeIds.has(e.source) && allNodeIds.has(e.target),
      );

      const existingEdgeIds = new Set(edges.map((e) => e.id));
      const uniqueNewEdges = validNewEdges.filter((e) => !existingEdgeIds.has(e.id));

      for (const node of uniqueNewNodes) {
        if (node.data.kind === 'method' || node.data.kind === 'function' || node.data.kind === 'class') {
          node.data.hasOutgoingCalls = true;
        }
      }

      const updatedNodes = nodes.map((n) =>
        n.id === sid ? { ...n, data: { ...n.data, isExpanded: true } } : n,
      );

      const nextExpanded = new Set(expandedCallNodes);
      nextExpanded.add(sid);

      const involvedFileIds = new Set(get().involvedFileIds);
      for (const n of uniqueNewNodes) {
        if (n.data.fileId) involvedFileIds.add(n.data.fileId);
      }

      set({
        nodes: [...updatedNodes, ...uniqueNewNodes],
        edges: [...edges, ...uniqueNewEdges],
        expandedCallNodes: nextExpanded,
        involvedFileIds,
      });
    } catch {
      // silently fail
    }
  },

  loadFullChain: async (projectId, symbolId) => {
    set({ loading: true });
    try {
      const data = await api.getFullChain(projectId, symbolId);

      const nodes: CustomNode[] = data.nodes.map((n) => buildNode(n));
      const edges: CustomEdge[] = data.edges.map((e) => buildEdge(e));

      const callerIds = new Set(edges.filter((e) => e.data.type === 'call').map((e) => e.source));

      for (const node of nodes) {
        node.data.hasOutgoingCalls = callerIds.has(node.id);
        node.data.isExpanded = callerIds.has(node.id);
      }

      const nextExpanded = new Set(
        nodes.filter((n) => n.data.isExpanded).map((n) => n.id),
      );

      const involvedFileIds = new Set(
        nodes.map((n) => n.data.fileId).filter(Boolean) as string[],
      );

      set({
        nodes,
        edges,
        loading: false,
        expandedCallNodes: nextExpanded,
        expandedNodes: new Set(),
        involvedFileIds,
      });
    } catch {
      set({ loading: false });
    }
  },

  selectNode: (node) => set({ selectedNode: node }),

  expandNode: async (projectId, nodeId) => {
    const { expandedNodes, nodes, edges } = get();
    if (expandedNodes.has(nodeId)) return;

    try {
      const data = await api.expandSymbol(projectId, nodeId);

      const newNodes: CustomNode[] = data.child_nodes.map((n: any) => buildNode(n));
      const newEdges: CustomEdge[] = data.edges.map((e: any) => buildEdge(e));

      const existingIds = new Set(nodes.map((n) => n.id));
      const uniqueNewNodes = newNodes.filter((n) => !existingIds.has(n.id));

      const allNodeIds = new Set([...nodes.map((n) => n.id), ...newNodes.map((n) => n.id)]);
      const validNewEdges = newEdges.filter(
        (e) => allNodeIds.has(e.source) && allNodeIds.has(e.target),
      );

      const existingEdgeIds = new Set(edges.map((e) => e.id));
      const uniqueNewEdges = validNewEdges.filter((e) => !existingEdgeIds.has(e.id));

      const nextExpanded = new Set(expandedNodes);
      nextExpanded.add(nodeId);

      const involvedFileIds = new Set(get().involvedFileIds);
      for (const n of uniqueNewNodes) {
        if (n.data.fileId) involvedFileIds.add(n.data.fileId);
      }

      set({
        nodes: [...nodes, ...uniqueNewNodes],
        edges: [...edges, ...uniqueNewEdges],
        expandedNodes: nextExpanded,
        involvedFileIds,
      });
    } catch {
      // silently fail
    }
  },

  collapseNode: (nodeId) => {
    const { expandedNodes, nodes, edges } = get();
    if (!expandedNodes.has(nodeId)) return;

    const childIds = new Set(
      nodes.filter((n) => n.data.parentId === nodeId).map((n) => n.id),
    );

    const nextExpanded = new Set(expandedNodes);
    nextExpanded.delete(nodeId);

    set({
      nodes: nodes.filter((n) => !childIds.has(n.id)),
      edges: edges.filter((e) => !childIds.has(e.source) && !childIds.has(e.target)),
      expandedNodes: nextExpanded,
    });
  },

  collapseCallNode: (nodeId) => {
    const { expandedCallNodes, nodes, edges } = get();
    if (!expandedCallNodes.has(nodeId)) return;

    const outgoingEdges = edges.filter((e) => e.source === nodeId);
    const directCalleeIds = new Set(outgoingEdges.map((e) => e.target));

    const toRemove = new Set<string>();
    const queue = Array.from(directCalleeIds);
    while (queue.length > 0) {
      const id = queue.pop()!;
      if (toRemove.has(id)) continue;
      toRemove.add(id);
      const childEdges = edges.filter((e) => e.source === id);
      for (const e of childEdges) {
        queue.push(e.target);
      }
    }

    const nextExpanded = new Set(expandedCallNodes);
    nextExpanded.delete(nodeId);
    for (const id of toRemove) {
      nextExpanded.delete(id);
    }

    const updatedNodes = nodes.map((n) =>
      toRemove.has(n.id) ? null : n.id === nodeId ? { ...n, data: { ...n.data, isExpanded: false } } : n,
    ).filter(Boolean) as CustomNode[];

    const involvedFileIds = new Set(
      updatedNodes.map((n) => n.data.fileId).filter(Boolean) as string[],
    );

    set({
      nodes: updatedNodes,
      edges: edges.filter((e) => !toRemove.has(e.source) && !toRemove.has(e.target)),
      expandedCallNodes: nextExpanded,
      involvedFileIds,
    });
  },

  focusOnNode: (nodeId) => {
    const { focusNodeId, focusStack } = get();
    const nextStack = focusNodeId ? [...focusStack, focusNodeId] : [...focusStack];
    set({ focusNodeId: nodeId, focusStack: nextStack });
  },

  focusBack: () => {
    const { focusStack } = get();
    if (focusStack.length === 0) {
      set({ focusNodeId: null, focusStack: [] });
    } else {
      const prev = focusStack[focusStack.length - 1];
      set({ focusNodeId: prev, focusStack: focusStack.slice(0, -1) });
    }
  },

  clear: () => set({ nodes: [], edges: [], selectedNode: null, selectedSymbol: null, expandedNodes: new Set(), expandedCallNodes: new Set(), chainFileId: null, involvedFileIds: new Set(), focusNodeId: null, focusStack: [] }),
}));
