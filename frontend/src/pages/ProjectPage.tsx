import { useEffect, useRef, useState } from 'react';
import { useProjectStore } from '@/store/projectStore';
import type { Project, ProjectStatus } from '@/types';
import './ProjectPage.css';

const POLL_INTERVAL = 3000;
const IN_PROGRESS_STATUSES: ProjectStatus[] = ['pending', 'cloning', 'parsing', 'indexing'];

export default function ProjectPage() {
  const { projects, loading, fetchProjects, createProject, deleteProject, selectProject } = useProjectStore();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [gitUrl, setGitUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Poll while any project is in a non-terminal status
  useEffect(() => {
    const hasInProgress = projects.some((p) => IN_PROGRESS_STATUSES.includes(p.status));

    if (hasInProgress && !pollingRef.current) {
      pollingRef.current = setInterval(() => {
        fetchProjects();
      }, POLL_INTERVAL);
    } else if (!hasInProgress && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [projects, fetchProjects]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await createProject(name, gitUrl, branch);
    setName('');
    setGitUrl('');
    setBranch('main');
    setShowForm(false);
  };

  const statusLabel: Record<string, string> = {
    pending: 'Pending',
    cloning: 'Cloning',
    parsing: 'Parsing',
    indexing: 'Indexing',
    ready: 'Ready',
    error: 'Error',
  };

  return (
    <div className="project-page">
      <div className="project-header">
        <h1>Projects</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ New Project'}
        </button>
      </div>

      {showForm && (
        <form className="project-form" onSubmit={handleSubmit}>
          <input placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input placeholder="Git URL" value={gitUrl} onChange={(e) => setGitUrl(e.target.value)} required />
          <input placeholder="Branch" value={branch} onChange={(e) => setBranch(e.target.value)} />
          <button className="btn btn-primary" type="submit">Create</button>
        </form>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : projects.length === 0 ? (
        <p className="empty-state">No projects yet. Create one to get started.</p>
      ) : (
        <div className="project-list">
          {projects.map((p: Project) => (
            <div key={p.id} className="project-card" onClick={() => selectProject(p.id)}>
              <div className="project-card-header">
                <h3>{p.name}</h3>
                <span className={`status-badge status-${p.status}`}>{statusLabel[p.status] || p.status}</span>
              </div>
              <p className="project-meta">{p.git_url}</p>
              <p className="project-meta">{p.language} / {p.branch}</p>
              <button
                className="btn btn-danger btn-sm"
                onClick={(e) => { e.stopPropagation(); deleteProject(p.id); }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
