import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { useComparisonStore } from '@/store/comparisonStore';
import type { ChangedFile, ChangeType, FileDiff } from '@/types';
import './ComparisonPage.css';

const changeLabels: Record<ChangeType, string> = {
  added: '新增', deleted: '删除', modified: '修改', renamed: '重命名', copied: '复制',
};

function CommitLabel({ sha, message, authoredAt }: { sha: string; message: string; authoredAt: string }) {
  return <><strong>{sha.slice(0, 7)}</strong><span>{message}</span><small>{new Date(authoredAt).toLocaleDateString()}</small></>;
}

function DiffLines({ patch }: { patch: string }) {
  return <div className="diff-lines">{patch.split('\n').map((line, index) => {
    const isHunk = line.startsWith('@@');
    const kind = isHunk ? 'hunk' : line.startsWith('+') ? 'added' : line.startsWith('-') ? 'deleted' : 'context';
    return <div className={`diff-line diff-line-${kind}`} key={`${index}-${line}`}>
      <span className="diff-line-number">{isHunk ? '↕' : index + 1}</span><span className="diff-line-mark">{isHunk ? '' : line[0] === '+' || line[0] === '-' ? line[0] : ' '}</span><code>{isHunk ? line : line.slice(1)}</code>
    </div>;
  })}</div>;
}

function FileItem({ file, selected, onClick }: { file: ChangedFile; selected: boolean; onClick: () => void }) {
  const path = file.new_path || file.old_path || '未知文件';
  return <button className={`file-item ${selected ? 'selected' : ''}`} onClick={onClick}>
    <span className={`change-badge change-${file.change_type}`}>{file.change_type[0].toUpperCase()}</span>
    <span className="file-item-main"><strong>{path.split('/').pop()}</strong><small>{path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '根目录'}</small></span>
    <span className="file-stats"><em>+{file.additions}</em><i>-{file.deletions}</i></span>
  </button>;
}

function FileDetail({ file, detail }: { file: ChangedFile; detail: FileDiff | null }) {
  const path = file.new_path || file.old_path || '未知文件';
  if (file.is_binary || detail?.is_binary) return <div className="detail-empty"><span className="empty-icon">◈</span><h3>二进制文件</h3><p>{path} 无法以文本形式展示。</p></div>;
  if (!detail) return <div className="detail-empty"><span className="empty-icon">⌁</span><h3>加载文件 Diff…</h3><p>正在读取 {path}</p></div>;
  return <>
    <div className="detail-header"><div><div className="detail-path">{path}</div>{file.old_path && file.new_path && file.old_path !== file.new_path && <div className="rename-path">{file.old_path} → {file.new_path}</div>}</div><span className={`detail-type type-${file.change_type}`}>{changeLabels[file.change_type]}</span></div>
    {detail.is_truncated && <div className="notice">内容过大，当前展示已截断。</div>}
    {detail.patch ? <DiffLines patch={detail.patch} /> : <div className="detail-empty compact"><h3>没有可显示的文本 Diff</h3><p>该文件可能是新增或删除文件，或内容为空。</p></div>}
  </>;
}

export default function ComparisonPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const s = useComparisonStore();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all' | ChangeType>('all');

  useEffect(() => { if (projectId) s.fetchCommits(projectId); }, [projectId]);
  const files = useMemo(() => s.diff?.files.filter((file) => {
    const path = file.new_path || file.old_path || '';
    return (filter === 'all' || file.change_type === filter) && path.toLowerCase().includes(query.toLowerCase());
  }) || [], [s.diff, query, filter]);
  const selectedPath = s.selectedFile?.new_path || s.selectedFile?.old_path;

  return <main className="comparison-page">
    <header className="comparison-heading"><div><Link to="/" className="back-link">← 项目列表</Link><h1>代码 Diff</h1><p>比较两个提交，逐文件审阅代码变更</p></div><div className="page-tab"><span className="tab-dot" />Diff 对比</div></header>
    <section className="comparison-controls panel"><div className="commit-select"><label>BASE<span>基准版本</span></label><select value={s.baseCommit} onChange={e => s.setBaseCommit(e.target.value)}>{s.commits.map(c => <option key={c.sha} value={c.sha}>{c.short_sha} · {c.message}</option>)}</select></div><span className="arrow">→</span><div className="commit-select"><label>HEAD<span>目标版本</span></label><select value={s.headCommit} onChange={e => s.setHeadCommit(e.target.value)}>{s.commits.map(c => <option key={c.sha} value={c.sha}>{c.short_sha} · {c.message}</option>)}</select></div><button className="compare-button" onClick={() => projectId && s.compare(projectId)} disabled={s.loading}>{s.loading ? '加载中…' : '查看 Diff'}</button></section>
    {s.commits.length > 0 && <div className="commit-context"><div><span>BASE</span><CommitLabel sha={s.commits.find(c => c.sha === s.baseCommit)?.sha || s.baseCommit} message={s.commits.find(c => c.sha === s.baseCommit)?.message || ''} authoredAt={s.commits.find(c => c.sha === s.baseCommit)?.authored_at || ''} /></div><div><span>HEAD</span><CommitLabel sha={s.commits.find(c => c.sha === s.headCommit)?.sha || s.headCommit} message={s.commits.find(c => c.sha === s.headCommit)?.message || ''} authoredAt={s.commits.find(c => c.sha === s.headCommit)?.authored_at || ''} /></div></div>}
    {s.error && <div className="comparison-error">⚠ {s.error}</div>}
    {!s.diff && !s.error && <div className="empty-panel"><span>⌘</span><h2>选择两个提交开始比较</h2><p>选择 Base 和 Head 后，点击“查看 Diff”</p></div>}
    {s.diff && <><section className="summary-grid"><div><strong>{s.diff.summary.files_changed}</strong><span>变更文件</span></div><div className="positive"><strong>+{s.diff.summary.additions}</strong><span>新增行</span></div><div className="negative"><strong>-{s.diff.summary.deletions}</strong><span>删除行</span></div><div><strong>{s.diff.summary.modified_files}</strong><span>修改文件</span></div></section><section className="diff-workspace panel"><aside className="file-sidebar"><div className="sidebar-heading"><div><h2>变更文件</h2><span>{files.length} / {s.diff.files.length} 个文件</span></div></div><div className="file-filters"><input value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索文件…" /><select value={filter} onChange={e => setFilter(e.target.value as 'all' | ChangeType)}><option value="all">全部类型</option><option value="added">新增</option><option value="modified">修改</option><option value="deleted">删除</option><option value="renamed">重命名</option></select></div><div className="file-list">{files.map((file, i) => <FileItem key={`${file.new_path}-${i}`} file={file} selected={selectedPath === (file.new_path || file.old_path)} onClick={() => projectId && s.selectFile(projectId, file)} />)}{files.length === 0 && <p className="list-empty">没有匹配的文件</p>}</div></aside><article className="file-detail">{s.selectedFile ? <FileDetail file={s.selectedFile} detail={s.fileDiff} /> : <div className="detail-empty"><span className="empty-icon">⌁</span><h3>选择一个文件</h3><p>从左侧列表选择文件查看详细修改</p></div>}</article></section></>}
  </main>;
}
