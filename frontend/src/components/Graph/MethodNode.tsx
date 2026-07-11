import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import type { CustomNodeData } from '@/types';
import './MethodNode.css';

export default function MethodNode({ data, selected }: NodeProps<CustomNodeData>) {
  const showExpand = data.hasOutgoingCalls && !data.isExpanded;
  const showExpanded = data.isExpanded;

  return (
    <div className={`mn-node${selected ? ' mn-selected' : ''}`} style={{ borderColor: data.color }}>
      <Handle type="target" position={Position.Top} className="mn-handle" />
      <div className="mn-body">
        <span className="mn-badge" style={{ background: data.color }}>M</span>
        <div className="mn-text">
          <span className="mn-label" title={data.signature || data.label}>{data.label}</span>
          {data.signature && <span className="mn-signature">{data.signature}</span>}
        </div>
        {showExpand && <span className="mn-expand-hint" title="单击展开调用">+</span>}
        {showExpanded && <span className="mn-expand-hint mn-expanded" title="已展开，单击收起">−</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="mn-handle" />
    </div>
  );
}
