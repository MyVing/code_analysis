import { useEffect, useState } from 'react';
import { useProjectStore } from '@/store/projectStore';
import type { Project } from '@/types';
import './ProjectPage.css';

export default function ProjectPage() {
  const { projects, loading, fetchProjects, createProject, deleteProject, selectProject } = useProjectStore();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [gitUrl, setGitUrl] = useState('');
  const [branch, setBranch] = useState('main');

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

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
