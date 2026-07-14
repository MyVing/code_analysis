import { useEffect, useMemo, useRef, useCallback, useState } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  type OnNodeClick,
  type OnEdgeClick,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import ClassNode from './ClassNode';
import MethodNode from './MethodNode';
import FieldNode from './FieldNode';
import CallEdge from './CallEdge';
import { layoutGraph, layoutIncremental } from './layout';
import type { CustomNode, CustomEdge, CustomNodeData } from '@/types';
import './Graph.css';

const NODE_TYPES = {
  classNode: ClassNode,
  methodNode: MethodNode,
  fieldNode: FieldNode,
};

const EDGE_TYPES = {
  call: CallEdge,
};

interface GraphProps {
  nodes: CustomNode[];
  edges: CustomEdge[];
  focusNodeId?: string | null;
  onNodeClick?: OnNodeClick<CustomNode>;
  onNodeDoubleClick?: OnNodeClick<CustomNode>;
  onEdgeClick?: OnEdgeClick<CustomEdge>;
  onPaneClick?: () => void;
}

function GraphInner({ nodes: rawNodes, edges: rawEdges, focusNodeId, onNodeClick, onNodeDoubleClick, onEdgeClick, onPaneClick }: GraphProps) {
  // Track previous node IDs to detect additions vs. removals vs. repositions
  const prevNodeIdsRef = useRef<Set<string>>(new Set());
  const prevLayoutNodesRef = useRef<CustomNode[]>([]);

  const [layoutedNodes, setLayoutedNodes] = useState<CustomNode[]>([]);
  const [layoutedEdges, setLayoutedEdges] = useState<CustomEdge[]>([]);

  // Debounce timer ref for layout recalculation
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const currentIds = new Set(rawNodes.map((n) => n.id));
    const prevIds = prevNodeIdsRef.current;
    const prevLayoutNodes = prevLayoutNodesRef.current;

    // Determine what changed
    const addedIds = new Set([...currentIds].filter((id) => !prevIds.has(id)));
    const removedIds = new Set([...prevIds].filter((id) => !currentIds.has(id)));

    const computeLayout = () => {
      if (prevLayoutNodes.length === 0 || removedIds.size > 0) {
        // Full layout: initial load or nodes were removed
        const result = layoutGraph(rawNodes, rawEdges);
        setLayoutedNodes(result.nodes as CustomNode[]);
        setLayoutedEdges(result.edges as CustomEdge[]);
        prevLayoutNodesRef.current = result.nodes as CustomNode[];
      } else if (addedIds.size > 0) {
        // Incremental layout: only position new nodes
        const newNodes = rawNodes.filter((n) => addedIds.has(n.id));
        const allEdges = rawEdges;
        const resultNodes = layoutIncremental(prevLayoutNodes, newNodes, allEdges);
        setLayoutedNodes(resultNodes as CustomNode[]);
        setLayoutedEdges(allEdges as CustomEdge[]);
        prevLayoutNodesRef.current = resultNodes as CustomNode[];
      } else {
        // No node count change (e.g. drag, data update) — skip layout entirely
        setLayoutedNodes(rawNodes);
        setLayoutedEdges(rawEdges);
      }
      prevNodeIdsRef.current = currentIds;
    };

    // Debounce: delay layout to coalesce rapid expand operations
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(computeLayout, 50);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [rawNodes, rawEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);
  const { fitView } = useReactFlow();
  const prevNodeCountRef = useRef(layoutedNodes.length);

  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  // fitView when node count changes (focus switch, expand/collapse)
  useEffect(() => {
    if (prevNodeCountRef.current !== layoutedNodes.length) {
      prevNodeCountRef.current = layoutedNodes.length;
      requestAnimationFrame(() => {
        fitView({ padding: 0.2, duration: 300 });
      });
    }
  }, [layoutedNodes.length, fitView]);

  // Focus on a specific node when focusNodeId changes
  useEffect(() => {
    if (focusNodeId) {
      requestAnimationFrame(() => {
        fitView({ nodes: [{ id: focusNodeId }], padding: 0.3, duration: 400 });
      });
    }
  }, [focusNodeId, fitView]);

  const defaultEdgeOptions = useMemo(
    () => ({
      type: 'call',
      animated: false,
    }),
    [],
  );

  return (
    <div className="graph-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Controls position="bottom-left" />
        <MiniMap
          position="bottom-right"
          nodeColor={(n) => {
            const data = n.data as CustomNodeData;
            return data?.color || '#6b7280';
          }}
          maskColor="rgba(0,0,0,0.1)"
        />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
      </ReactFlow>
    </div>
  );
}

export default function Graph(props: GraphProps) {
  return (
    <ReactFlowProvider>
      <GraphInner {...props} />
    </ReactFlowProvider>
  );
}
