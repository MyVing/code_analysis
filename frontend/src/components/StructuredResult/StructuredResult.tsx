import { useState } from 'react';
import './StructuredResult.css';

interface StructuredResultViewProps {
  data: Record<string, any>;
  schema?: Record<string, any>;
}

export default function StructuredResultView({ data, schema }: StructuredResultViewProps) {
  const [viewMode, setViewMode] = useState<'tree' | 'raw'>('tree');

  return (
    <div className="sr">
      <div className="sr-header">
        <span className="sr-badge">JSON</span>
        <span className="sr-title">结构化分析结果</span>
        <div className="sr-mode-switch">
          <button
            className={`sr-mode-btn ${viewMode === 'tree' ? 'sr-mode-active' : ''}`}
            onClick={() => setViewMode('tree')}
          >
            树形
          </button>
          <button
            className={`sr-mode-btn ${viewMode === 'raw' ? 'sr-mode-active' : ''}`}
            onClick={() => setViewMode('raw')}
          >
            原始
          </button>
        </div>
      </div>
      <div className="sr-body">
        {viewMode === 'tree' ? (
          <JsonNode value={data} depth={0} isRoot defaultExpanded />
        ) : (
          <pre className="sr-raw"><code>{JSON.stringify(data, null, 2)}</code></pre>
        )}
      </div>
    </div>
  );
}

interface JsonNodeProps {
  value: any;
  depth: number;
  isRoot?: boolean;
  defaultExpanded?: boolean;
  keyName?: string;
}

function JsonNode({ value, depth, isRoot, defaultExpanded, keyName }: JsonNodeProps) {
  const [collapsed, setCollapsed] = useState(!(defaultExpanded ?? depth < 2));

  if (value === null || value === undefined) {
    return (
      <div className="jn-line" style={{ paddingLeft: isRoot ? 0 : depth * 20 }}>
        {keyName !== undefined && <><span className="jn-key">"{keyName}"</span><span className="jn-colon">: </span></>}
        <span className="jn-null">null</span>
      </div>
    );
  }

  if (typeof value !== 'object') {
    return (
      <div className="jn-line" style={{ paddingLeft: isRoot ? 0 : depth * 20 }}>
        {keyName !== undefined && <><span className="jn-key">"{keyName}"</span><span className="jn-colon">: </span></>}
        <JsonValue value={value} />
      </div>
    );
  }

  const isArray = Array.isArray(value);
  const entries = isArray
    ? value.map((v: any, i: number) => [String(i), v] as [string, any])
    : Object.entries(value);
  const open = isArray ? '[' : '{';
  const close = isArray ? ']' : '}';

  if (entries.length === 0) {
    return (
      <div className="jn-line" style={{ paddingLeft: isRoot ? 0 : depth * 20 }}>
        {keyName !== undefined && <><span className="jn-key">"{keyName}"</span><span className="jn-colon">: </span></>}
        <span className="jn-bracket">{open}{close}</span>
      </div>
    );
  }

  if (collapsed) {
    return (
      <div className="jn-line" style={{ paddingLeft: isRoot ? 0 : depth * 20 }}>
        <span className="jn-toggle" onClick={() => setCollapsed(false)}>▶</span>
        {keyName !== undefined && <><span className="jn-key">"{keyName}"</span><span className="jn-colon">: </span></>}
        <span className="jn-bracket">{open}</span>
        <span className="jn-ellipsis"> ... </span>
        <span className="jn-bracket">{close}</span>
        <span className="jn-count">{isArray ? `${value.length} items` : `${entries.length} keys`}</span>
      </div>
    );
  }

  return (
    <div style={{ paddingLeft: isRoot ? 0 : 0 }}>
      <div className="jn-line" style={{ paddingLeft: isRoot ? 0 : depth * 20 }}>
        <span className="jn-toggle" onClick={() => setCollapsed(true)}>▼</span>
        {keyName !== undefined && <><span className="jn-key">"{keyName}"</span><span className="jn-colon">: </span></>}
        <span className="jn-bracket">{open}</span>
      </div>
      {entries.map(([k, v], i) => (
        <div key={k}>
          <JsonNode
            value={v}
            depth={depth + 1}
            keyName={isArray ? undefined : k}
            defaultExpanded={depth < 2}
          />
          {i < entries.length - 1 && (
            <span className="jn-comma" style={{ paddingLeft: (depth + 1) * 20 }}></span>
          )}
        </div>
      ))}
      <div className="jn-line" style={{ paddingLeft: isRoot ? 0 : depth * 20 }}>
        <span className="jn-bracket">{close}</span>
      </div>
    </div>
  );
}

function JsonValue({ value }: { value: any }) {
  if (typeof value === 'string') {
    return <span className="jn-string">"{value}"</span>;
  }
  if (typeof value === 'number') {
    return <span className="jn-number">{value}</span>;
  }
  if (typeof value === 'boolean') {
    return <span className="jn-boolean">{String(value)}</span>;
  }
  return <span className="jn-string">{String(value)}</span>;
}
