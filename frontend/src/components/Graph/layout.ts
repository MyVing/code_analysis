import dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 40;
const METHOD_NODE_WIDTH = 200;
const METHOD_NODE_HEIGHT = 36;
const FIELD_NODE_WIDTH = 160;
const FIELD_NODE_HEIGHT = 28;

export function layoutGraph(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB',
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 50, ranksep: 60, marginx: 40, marginy: 40 });

  for (const node of nodes) {
    const nodeType = node.data?.type;
    let width = NODE_WIDTH;
    let height = NODE_HEIGHT;
    if (nodeType === 'methodNode') {
      width = METHOD_NODE_WIDTH;
      height = METHOD_NODE_HEIGHT;
    } else if (nodeType === 'fieldNode') {
      width = FIELD_NODE_WIDTH;
      height = FIELD_NODE_HEIGHT;
    }
    g.setNode(node.id, { width, height });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    const nodeType = node.data?.type;
    let width = NODE_WIDTH;
    let height = NODE_HEIGHT;
    if (nodeType === 'methodNode') {
      width = METHOD_NODE_WIDTH;
      height = METHOD_NODE_HEIGHT;
    } else if (nodeType === 'fieldNode') {
      width = FIELD_NODE_WIDTH;
      height = FIELD_NODE_HEIGHT;
    }
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
