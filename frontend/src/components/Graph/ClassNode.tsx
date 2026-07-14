import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import type { CustomNodeData } from '@/types';
import './ClassNode.css';

export default function ClassNode({ data, selected }: NodeProps<CustomNodeData>) {
  const showExpand = data.hasOutgoingCalls && !data.isExpanded;
  const showExpanded = data.isExpanded;
  const badge = data.kind === 'interface' ? 'I' : data.kind === 'enum' ? 'E' : 'C';

  return (
    <div className={`cn-node${selected ? ' cn-selected' : ''}`} style={{ borderColor: data.color }}>
      <Handle type="target" position={Position.Top} className="cn-handle" />
      <div className="cn-body">
        <span className="cn-badge" style={{ background: data.color }}>{badge}</span>
        <div className="cn-text">
          <span className="cn-label">{data.label}</span>
          {data.modifiers && <span className="cn-modifiers">{data.modifiers}</span>}
        </div>
        {showExpand && <span className="cn-expand-hint" title="单击展开一层 / 双击展开完整链路">▸</span>}
        {showExpanded && <span className="cn-expand-hint cn-expanded" title="已展开，单击收起">▾</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="cn-handle" />
    </div>
  );
}
