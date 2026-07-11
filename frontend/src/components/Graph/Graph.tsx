import { useEffect, useMemo, useRef, useCallback } from 'react';
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
import { layoutGraph } from './layout';
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
  onNodeClick?: OnNodeClick<CustomNode>;
  onNodeDoubleClick?: OnNodeClick<CustomNode>;
  onEdgeClick?: OnEdgeClick<CustomEdge>;
  onPaneClick?: () => void;
}

function GraphInner({ nodes: rawNodes, edges: rawEdges, onNodeClick, onNodeDoubleClick, onEdgeClick, onPaneClick }: GraphProps) {
  const layouted = useMemo(
    () => layoutGraph(rawNodes, rawEdges),
    [rawNodes, rawEdges],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layouted.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layouted.edges);
  const { fitView } = useReactFlow();
  const prevNodeCountRef = useRef(layouted.nodes.length);

  useEffect(() => {
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
  }, [layouted, setNodes, setEdges]);

  // fitView when node count changes (focus switch, expand/collapse)
  useEffect(() => {
    if (prevNodeCountRef.current !== layouted.nodes.length) {
      prevNodeCountRef.current = layouted.nodes.length;
      // Delay to let React Flow process the node changes first
      requestAnimationFrame(() => {
        fitView({ padding: 0.2, duration: 300 });
      });
    }
  }, [layouted.nodes.length, fitView]);

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
