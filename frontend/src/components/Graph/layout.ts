import dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 40;
const METHOD_NODE_WIDTH = 200;
const METHOD_NODE_HEIGHT = 36;
const FIELD_NODE_WIDTH = 160;
const FIELD_NODE_HEIGHT = 28;

function getNodeSize(nodeType?: string) {
  if (nodeType === 'methodNode') return { width: METHOD_NODE_WIDTH, height: METHOD_NODE_HEIGHT };
  if (nodeType === 'fieldNode') return { width: FIELD_NODE_WIDTH, height: FIELD_NODE_HEIGHT };
  return { width: NODE_WIDTH, height: NODE_HEIGHT };
}

export function layoutGraph(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB',
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 50, ranksep: 60, marginx: 40, marginy: 40 });

  for (const node of nodes) {
    const { width, height } = getNodeSize(node.data?.type);
    g.setNode(node.id, { width, height });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    const { width, height } = getNodeSize(node.data?.type);
    return {
      ...node,
      position: {
        x: pos.x - width / 2,
        y: pos.y - height / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

/** Incremental layout: position only new nodes relative to existing ones, keeping existing positions intact. */
export function layoutIncremental(
  existingNodes: Node[],
  newNodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB',
): Node[] {
  if (newNodes.length === 0) return existingNodes;

  const existingMap = new Map(existingNodes.map((n) => [n.id, n]));
  const allNodes = [...existingNodes, ...newNodes];

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 50, ranksep: 60, marginx: 40, marginy: 40 });

  for (const node of allNodes) {
    const { width, height } = getNodeSize(node.data?.type);
    // Pin existing nodes at their current positions so dagre respects them
    if (existingMap.has(node.id)) {
      const pos = existingMap.get(node.id)!.position;
      g.setNode(node.id, { width, height, x: pos.x + width / 2, y: pos.y + height / 2 });
    } else {
      g.setNode(node.id, { width, height });
    }
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  // Only update positions for new nodes; keep existing nodes unchanged
  const newPositions = new Map<string, { x: number; y: number }>();
  for (const node of newNodes) {
    const pos = g.node(node.id);
    if (pos) {
      const { width, height } = getNodeSize(node.data?.type);
      newPositions.set(node.id, { x: pos.x - width / 2, y: pos.y - height / 2 });
    }
  }

  return allNodes.map((node) => {
    const newPos = newPositions.get(node.id);
    if (newPos) {
      return { ...node, position: newPos };
    }
    return node;
  });
}
