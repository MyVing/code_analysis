import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { useProjectStore } from '@/store/projectStore';
import { useGraphStore } from '@/store/graphStore';
import { api } from '@/services/api';
import ResizablePanel from '@/components/ResizablePanel/ResizablePanel';
import FileTree, { type FileTreeRef } from '@/components/FileTree/FileTree';
import Graph from '@/components/Graph/Graph';
import CodeViewer from '@/components/CodeViewer/CodeViewer';
import type { CustomNode, Symbol } from '@/types';
import './AnalysisPage.css';

export default function AnalysisPage() {
  const { currentProject } = useProjectStore();
  const {
    nodes, edges, loading, expandedCallNodes, chainFileId, involvedFileIds,
    focusNodeId, focusStack,
    loadFileChain, expandCall, expandClassCalls, loadFullChain,
    selectNode, selectedNode,
    focusOnNode, focusBack,
  } = useGraphStore();
  const navigate = useNavigate();
  const fileTreeRef = useRef<FileTreeRef>(null);

  const [codeContent, setCodeContent] = useState<string | null>(null);
  const [codeLanguage, setCodeLanguage] = useState('java');
  const [codeFilePath, setCodeFilePath] = useState<string | undefined>();
  const [highlightStart, setHighlightStart] = useState<number | undefined>();
  const [highlightEnd, setHighlightEnd] = useState<number | undefined>();

  // Auto-expand file tree for involved files
  useEffect(() => {
    if (!involvedFileIds || involvedFileIds.size === 0) return;
    // Find file paths for involved file IDs from current nodes
    const filePaths = new Set<string>();
    for (const node of nodes) {
      if (node.data.fileId && involvedFileIds.has(node.data.fileId) && node.data.filePath) {
        filePaths.add(node.data.filePath);
      }
    }
    for (const fp of filePaths) {
      fileTreeRef.current?.expandToFile(fp);
    }
  }, [involvedFileIds, nodes]);

  const loadFileContent = useCallback(async (fileId: string, lang?: string, startLine?: number, endLine?: number) => {
    try {
      const data = await api.getFileContent(fileId);
      setCodeContent(data.content);
      setCodeLanguage(data.language || lang || 'java');
      setCodeFilePath(data.file_path);
      // Set highlight after content is loaded to ensure correct positioning
      if (startLine != null && endLine != null) {
        setHighlightStart(startLine);
        setHighlightEnd(endLine);
      } else {
        setHighlightStart(undefined);
        setHighlightEnd(undefined);
      }
    } catch {
      setCodeContent(null);
    }
  }, []);

  const handleNodeClick = useCallback(
    (_: any, node: CustomNode) => {
      selectNode(node);

      if (!currentProject) return;

      const nodeId = node.id;
      const isExpanded = expandedCallNodes.has(nodeId);

      if (isExpanded) {
        // Already expanded — focus on this node's downstream subgraph instead of collapsing
        focusOnNode(nodeId);
      } else if (node.data.hasOutgoingCalls) {
        // Has outgoing calls but not expanded — expand and focus
        focusOnNode(nodeId);
      } else {
        // Leaf node — just focus on it
        focusOnNode(nodeId);
      }

      // Load source code
      const fileId = node.data.fileId;
      if (fileId) {
        loadFileContent(fileId, node.data.kind, node.data.startLine, node.data.endLine);
      }
    },
    [selectNode, expandedCallNodes, focusOnNode, currentProject, loadFileContent],
  );

  const handleNodeDoubleClick = useCallback(
    (_: any, node: CustomNode) => {
      if (!currentProject) return;
      if (node.data.type === 'classNode' || node.data.type === 'methodNode') {
        loadFullChain(currentProject.id, node.id);
      }
    },
    [loadFullChain, currentProject],
  );

  const handleFileSelect = useCallback(
    (file: { id: string; file_path: string; language: string }) => {
      loadFileContent(file.id, file.language);
    },
    [loadFileContent],
  );

  const handleFileChainSelect = useCallback(
    (file: { id: string; file_path: string; language: string }) => {
      if (currentProject) {
        loadFileChain(currentProject.id, file.id);
      }
    },
    [loadFileChain, currentProject],
  );

  const handleSymbolClick = useCallback(
    (symbol: Symbol) => {
      loadFileContent(symbol.file_id, undefined, symbol.start_line, symbol.end_line);
    },
    [loadFileContent],
  );

  const handlePaneClick = useCallback(() => {
    selectNode(null);
    focusBack();
  }, [selectNode, focusBack]);

  // Focus filtering: when focusNodeId is set, show that node + downstream + upstream ancestors
  const { filteredNodes, filteredEdges } = useMemo(() => {
    if (!focusNodeId) {
      return { filteredNodes: nodes, filteredEdges: edges };
    }
    // BFS downstream from focusNodeId
    const reachable = new Set<string>();
    reachable.add(focusNodeId);
    const queue = [focusNodeId];
    while (queue.length > 0) {
      const current = queue.pop()!;
      for (const edge of edges) {
        if (edge.source === current && !reachable.has(edge.target)) {
          reachable.add(edge.target);
          queue.push(edge.target);
        }
      }
    }
    // BFS upstream: trace back from focusNodeId to include ancestor path
    const upstream = new Set<string>();
    const upstreamQueue = [focusNodeId];
    while (upstreamQueue.length > 0) {
      const current = upstreamQueue.pop()!;
      for (const edge of edges) {
        if (edge.target === current && !upstream.has(edge.source) && !reachable.has(edge.source)) {
          upstream.add(edge.source);
          upstreamQueue.push(edge.source);
        }
      }
    }
    const allReachable = new Set([...reachable, ...upstream]);
    const fNodes = nodes.filter((n) => allReachable.has(n.id));
    const fEdges = edges.filter((e) => allReachable.has(e.source) && allReachable.has(e.target));
    return { filteredNodes: fNodes, filteredEdges: fEdges };
  }, [focusNodeId, nodes, edges]);

  const handleAskAI = useCallback(() => {
    if (selectedNode && currentProject) {
      navigate(`/chat?projectId=${currentProject.id}&question=${encodeURIComponent(`分析 ${selectedNode.data.label} 的调用链`)}`);
    }
  }, [selectedNode, currentProject, navigate]);

  // Build highlight file paths set from involvedFileIds
  const highlightFilePaths = new Set<string>();
  for (const node of nodes) {
    if (node.data.fileId && involvedFileIds.has(node.data.fileId) && node.data.filePath) {
      highlightFilePaths.add(node.data.filePath);
    }
  }

  if (!currentProject) {
    return (
      <div className="analysis-page">
        <p className="empty-state">Select a project first.</p>
      </div>
    );
  }

  return (
    <div className="analysis-page">
      <div className="analysis-header">
        <h1>{currentProject.name}</h1>
        <span className={`status-badge status-${currentProject.status}`}>{currentProject.status}</span>
        <div className="analysis-actions">
          {currentProject.status === 'ready' && chainFileId && (
            <button className="btn btn-sm" onClick={() => loadFileChain(currentProject.id, chainFileId)}>
              Refresh Graph
            </button>
          )}
          {selectedNode && (
            <button className="btn btn-primary btn-sm" onClick={handleAskAI}>
              Ask AI about {selectedNode.data.label}
            </button>
          )}
        </div>
      </div>

      {currentProject.status !== 'ready' ? (
        <div className="analysis-empty">
          <p>Project status: {currentProject.status}</p>
          <p className="hint">Wait for analysis to complete.</p>
        </div>
      ) : loading ? (
        <div className="analysis-empty">
          <p>Loading graph...</p>
        </div>
      ) : (
        <div className="analysis-body">
          <ResizablePanel
            panels={[
              {
                id: 'filetree',
                content: (
                  <FileTree
                    ref={fileTreeRef}
                    projectId={currentProject.id}
                    onFileSelect={handleFileSelect}
                    onSymbolSelect={handleSymbolClick}
                    onFileChainSelect={handleFileChainSelect}
                    highlightFilePaths={highlightFilePaths}
                  />
                ),
                defaultSize: 18,
                minSize: 12,
              },
              {
                id: 'graph',
                content: (
                  <div className="graph-panel-inner">
                    {focusNodeId && (
                      <div className="focus-breadcrumb">
                        <button className="btn btn-sm focus-back-btn" onClick={focusBack}>
                          ← 返回上级
                        </button>
                        <span className="focus-current">
                          {nodes.find((n) => n.id === focusNodeId)?.data.label || focusNodeId}
                        </span>
                        {focusStack.length > 0 && (
                          <span className="focus-depth">（第 {focusStack.length + 1} 层）</span>
                        )}
                      </div>
                    )}
                    {nodes.length === 0 ? (
                      <div className="analysis-empty">
                        <p>Click a file in the left panel to view its call chain.</p>
                      </div>
                    ) : (
                      <Graph
                        nodes={filteredNodes}
                        edges={filteredEdges}
                        focusNodeId={focusNodeId}
                        onNodeClick={handleNodeClick}
                        onNodeDoubleClick={handleNodeDoubleClick}
                        onPaneClick={handlePaneClick}
                      />
                    )}
                  </div>
                ),
                defaultSize: 52,
                minSize: 30,
              },
              {
                id: 'code',
                content: (
                  <CodeViewer
                    content={codeContent}
                    language={codeLanguage}
                    filePath={codeFilePath}
                    highlightStart={highlightStart}
                    highlightEnd={highlightEnd}
                  />
                ),
                defaultSize: 30,
                minSize: 20,
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
