import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import type { CustomEdgeData } from '@/types';
import './CallEdge.css';

export default function CallEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<CustomEdgeData>) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 8,
  });

  const edgeType = data?.type || 'call';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        className={`ce-edge ce-${edgeType}${selected ? ' ce-selected' : ''}`}
      />
      {data?.lineNumber && (
        <EdgeLabelRenderer>
          <div
            className="ce-label"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
            }}
          >
            L{data.lineNumber}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
