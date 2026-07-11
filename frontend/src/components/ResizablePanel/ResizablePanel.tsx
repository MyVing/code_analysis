import { useState, useRef, useCallback, type ReactNode } from 'react';
import './ResizablePanel.css';

interface Panel {
  id: string;
  content: ReactNode;
  defaultSize: number;
  minSize?: number;
}

interface ResizablePanelProps {
  panels: Panel[];
  direction?: 'horizontal' | 'vertical';
}

export default function ResizablePanel({ panels, direction = 'horizontal' }: ResizablePanelProps) {
  const [sizes, setSizes] = useState(() => panels.map((p) => p.defaultSize));
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<{ index: number; startPos: number; startSizes: number[] } | null>(null);

  const onMouseDown = useCallback(
    (index: number, e: React.MouseEvent) => {
      e.preventDefault();
      const startPos = direction === 'horizontal' ? e.clientX : e.clientY;
      dragging.current = { index, startPos, startSizes: [...sizes] };
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
      document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
      document.body.style.userSelect = 'none';
    },
    [sizes, direction],
  );

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const { index, startPos, startSizes } = dragging.current;
      const containerSize =
        direction === 'horizontal' ? containerRef.current.offsetWidth : containerRef.current.offsetHeight;
      const delta = (direction === 'horizontal' ? e.clientX : e.clientY) - startPos;
      const deltaPercent = (delta / containerSize) * 100;

      const minA = panels[index].minSize ?? 10;
      const minB = panels[index + 1].minSize ?? 10;

      let newA = startSizes[index] + deltaPercent;
      let newB = startSizes[index + 1] - deltaPercent;

      if (newA < minA) {
        newB -= minA - newA;
        newA = minA;
      }
      if (newB < minB) {
        newA -= minB - newB;
        newB = minB;
      }

      const next = [...startSizes];
      next[index] = newA;
      next[index + 1] = newB;
      setSizes(next);
    },
    [panels, direction],
  );

  const onMouseUp = useCallback(() => {
    dragging.current = null;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, [onMouseMove]);

  const children: ReactNode[] = [];
  panels.forEach((panel, i) => {
    children.push(
      <div
        key={panel.id}
        className="rp-panel"
        style={{ [direction === 'horizontal' ? 'width' : 'height']: `${sizes[i]}%` }}
      >
        {panel.content}
      </div>,
    );
    if (i < panels.length - 1) {
      children.push(
        <div
          key={`divider-${i}`}
          className={`rp-divider rp-divider-${direction}`}
          onMouseDown={(e) => onMouseDown(i, e)}
        />,
      );
    }
  });

  return (
    <div ref={containerRef} className={`rp-container rp-container-${direction}`}>
      {children}
    </div>
  );
}
