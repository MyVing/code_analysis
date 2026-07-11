import { useEffect, useRef, useState, useMemo } from 'react';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-java';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-bash';
import './CodeViewer.css';

const LANG_MAP: Record<string, string> = {
  java: 'java',
  python: 'python',
  py: 'python',
  typescript: 'typescript',
  ts: 'typescript',
  tsx: 'typescript',
  javascript: 'javascript',
  js: 'javascript',
  jsx: 'javascript',
  json: 'json',
  sql: 'sql',
  bash: 'bash',
  sh: 'bash',
  kotlin: 'java',
  scala: 'java',
  groovy: 'java',
};

interface CodeViewerProps {
  content: string | null;
  language?: string;
  filePath?: string;
  highlightStart?: number;
  highlightEnd?: number;
  onLineClick?: (line: number) => void;
}

export default function CodeViewer({
  content,
  language = 'java',
  filePath,
  highlightStart,
  highlightEnd,
  onLineClick,
}: CodeViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  const prismLang = LANG_MAP[language] || 'java';

  // Highlight the entire content once, then split into lines for rendering
  const highlightedLines = useMemo(() => {
    if (!content) return [];
    const grammar = Prism.languages[prismLang];
    if (!grammar) return content.split('\n');
    const highlighted = Prism.highlight(content, grammar, prismLang);
    return highlighted.split('\n');
  }, [content, prismLang]);

  useEffect(() => {
    if (highlightStart && containerRef.current && content) {
      const lineEl = containerRef.current.querySelector(`[data-line="${highlightStart}"]`);
      if (lineEl) {
        lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [highlightStart, content]);

  if (!content) {
    return (
      <div className="cv-empty">
        <p>Select a file or node to view source code.</p>
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-viewer">
      <div className="cv-header">
        <span className="cv-path">{filePath}</span>
        <button className="cv-copy" onClick={handleCopy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="cv-body" ref={containerRef}>
        <table className="cv-table">
          <tbody>
            {highlightedLines.map((line, i) => {
              const lineNum = i + 1;
              const isHighlighted =
                highlightStart != null &&
                highlightEnd != null &&
                lineNum >= highlightStart &&
                lineNum <= highlightEnd;
              return (
                <tr
                  key={lineNum}
                  data-line={lineNum}
                  className={`cv-row${isHighlighted ? ' cv-highlight' : ''}`}
                  onClick={() => onLineClick?.(lineNum)}
                >
                  <td className="cv-linenum">{lineNum}</td>
                  <td className="cv-linecontent">
                    <span dangerouslySetInnerHTML={{ __html: line || '&nbsp;' }} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
