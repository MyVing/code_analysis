import { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react';
import { api } from '@/services/api';
import type { Symbol } from '@/types';
import './FileTree.css';

interface FileItem {
  id: string;
  file_path: string;
  language: string;
}

export interface FileTreeRef {
  expandToFile: (filePath: string) => void;
}

interface FileTreeProps {
  projectId: string;
  onFileSelect?: (file: FileItem) => void;
  onSymbolSelect?: (symbol: Symbol) => void;
  onFileChainSelect?: (file: FileItem) => void;
  selectedFilePath?: string | null;
  highlightFilePaths?: Set<string>;
}

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
  fileId?: string;
  language?: string;
}

function buildTree(files: FileItem[]): TreeNode {
  const root: TreeNode = { name: '', path: '', isDir: true, children: [] };
  for (const file of files) {
    const parts = file.file_path.split('/');
    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1;
      let child = current.children.find((c) => c.name === part && c.isDir === !isFile);
      if (!child) {
        child = {
          name: part,
          path: parts.slice(0, i + 1).join('/'),
          isDir: !isFile,
          children: [],
          ...(isFile ? { fileId: file.id, language: file.language } : {}),
        };
        current.children.push(child);
      }
      current = child;
    }
  }
  sortTree(root);
  return root;
}

function sortTree(node: TreeNode) {
  node.children.sort((a, b) => {
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  node.children.forEach(sortTree);
}

const FileTree = forwardRef<FileTreeRef, FileTreeProps>(
  function FileTree({ projectId, onFileSelect, onSymbolSelect, onFileChainSelect, selectedFilePath, highlightFilePaths }, ref) {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [tree, setTree] = useState<TreeNode | null>(null);
    const [expanded, setExpanded] = useState<Set<string>>(new Set());
    const [symbols, setSymbols] = useState<Record<string, Symbol[]>>({});
    const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(false);

    useEffect(() => {
      if (!projectId) return;
      setLoading(true);
      api.listProjectFiles(projectId).then((data) => {
        const items: FileItem[] = data.map((f: any) => ({
          id: f.id,
          file_path: f.file_path,
          language: f.language,
        }));
        setFiles(items);
        setTree(buildTree(items));
        setLoading(false);
      }).catch(() => setLoading(false));
    }, [projectId]);

    const expandToFile = useCallback((filePath: string) => {
      const parts = filePath.split('/');
      const dirPaths: string[] = [];
      for (let i = 1; i < parts.length; i++) {
        dirPaths.push(parts.slice(0, i).join('/'));
      }
      setExpanded((prev) => {
        const next = new Set(prev);
        for (const dp of dirPaths) {
          next.add(dp);
        }
        return next;
      });
    }, []);

    useImperativeHandle(ref, () => ({ expandToFile }), [expandToFile]);

    const toggleDir = useCallback((path: string) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(path)) next.delete(path);
        else next.add(path);
        return next;
      });
    }, []);

    const toggleFileSymbols = useCallback(
      async (fileId: string) => {
        if (expandedFiles.has(fileId)) {
          setExpandedFiles((prev) => {
            const next = new Set(prev);
            next.delete(fileId);
            return next;
          });
          return;
        }
        if (!symbols[fileId]) {
          try {
            const syms = await api.getSymbolsByFile(fileId);
            setSymbols((prev) => ({ ...prev, [fileId]: syms }));
          } catch {
            return;
          }
        }
        setExpandedFiles((prev) => new Set(prev).add(fileId));
      },
      [expandedFiles, symbols],
    );

    const handleFileClick = useCallback(
      (file: FileItem) => {
        onFileSelect?.(file);
        onFileChainSelect?.(file);
        toggleFileSymbols(file.id);
      },
      [onFileSelect, onFileChainSelect, toggleFileSymbols],
    );

    if (loading) return <div className="ft-loading">Loading files...</div>;
    if (!tree) return <div className="ft-empty">No files</div>;

    return (
      <div className="file-tree">
        <div className="ft-header">Files</div>
        <div className="ft-content">
          {tree.children.map((child) => (
            <TreeNodeView
              key={child.path}
              node={child}
              depth={0}
              expanded={expanded}
              expandedFiles={expandedFiles}
              symbols={symbols}
              onToggleDir={toggleDir}
              onFileClick={handleFileClick}
              onSymbolClick={onSymbolSelect}
              selectedFilePath={selectedFilePath}
              highlightFilePaths={highlightFilePaths}
            />
          ))}
        </div>
      </div>
    );
  },
);

export default FileTree;

interface TreeNodeViewProps {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  expandedFiles: Set<string>;
  symbols: Record<string, Symbol[]>;
  onToggleDir: (path: string) => void;
  onFileClick: (file: FileItem) => void;
  onSymbolClick?: (symbol: Symbol) => void;
  selectedFilePath?: string | null;
  highlightFilePaths?: Set<string>;
}

function TreeNodeView({
  node,
  depth,
  expanded,
  expandedFiles,
  symbols,
  onToggleDir,
  onFileClick,
  onSymbolClick,
  selectedFilePath,
  highlightFilePaths,
}: TreeNodeViewProps) {
  const indent = depth * 16;

  if (node.isDir) {
    const isOpen = expanded.has(node.path);
    return (
      <div>
        <div
          className="ft-item ft-dir"
          style={{ paddingLeft: indent + 8 }}
          onClick={() => onToggleDir(node.path)}
        >
          <span className="ft-arrow">{isOpen ? '▾' : '▸'}</span>
          <span className="ft-icon">📁</span>
          <span className="ft-name">{node.name}</span>
        </div>
        {isOpen &&
          node.children.map((child) => (
            <TreeNodeView
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              expandedFiles={expandedFiles}
              symbols={symbols}
              onToggleDir={onToggleDir}
              onFileClick={onFileClick}
              onSymbolClick={onSymbolClick}
              selectedFilePath={selectedFilePath}
              highlightFilePaths={highlightFilePaths}
            />
          ))}
      </div>
    );
  }

  const isExpanded = expandedFiles.has(node.fileId!);
  const isSelected = selectedFilePath === node.path;
  const isHighlighted = highlightFilePaths?.has(node.path);
  const fileSyms = symbols[node.fileId!] || [];

  return (
    <div>
      <div
        className={`ft-item ft-file${isSelected ? ' ft-selected' : ''}${isHighlighted ? ' ft-highlighted' : ''}`}
        style={{ paddingLeft: indent + 8 }}
        onClick={() =>
          onFileClick({ id: node.fileId!, file_path: node.path, language: node.language! })
        }
      >
        <span className="ft-arrow">{isExpanded ? '▾' : '▸'}</span>
        <span className="ft-icon">📄</span>
        <span className="ft-name" title={node.path}>{node.name}</span>
      </div>
      {isExpanded && fileSyms.length > 0 && (
        <div className="ft-symbols">
          {fileSyms.map((sym) => (
            <div
              key={sym.id}
              className={`ft-symbol ft-symbol-${sym.kind}`}
              style={{ paddingLeft: indent + 24 }}
              onClick={(e) => {
                e.stopPropagation();
                onSymbolClick?.(sym);
              }}
            >
              <span className="ft-sym-icon">{sym.kind === 'class' ? 'C' : sym.kind === 'method' ? 'M' : sym.kind === 'interface' ? 'I' : sym.kind === 'variable' ? 'V' : 'F'}</span>
              <span className="ft-sym-name">{sym.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
