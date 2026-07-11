import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import type { CustomNodeData } from '@/types';
import './FieldNode.css';

export default function FieldNode({ data, selected }: NodeProps<CustomNodeData>) {
  return (
    <div className={`fn-node${selected ? ' fn-selected' : ''}`} style={{ borderColor: data.color }}>
      <Handle type="target" position={Position.Top} className="fn-handle" />
      <div className="fn-body">
        <span className="fn-badge" style={{ background: data.color }}>F</span>
        <span className="fn-label" title={data.signature || data.label}>{data.label}</span>
        {data.signature && <span className="fn-type">{data.signature}</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="fn-handle" />
    </div>
  );
}
