import { create } from 'zustand';
import type { Project, ProjectStatus } from '@/types';
import { api } from '@/services/api';

interface ProjectStore {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;

  fetchProjects: () => Promise<void>;
  selectProject: (id: string) => void;
  createProject: (name: string, gitUrl: string, branch?: string) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;
  updateProjectStatus: (id: string, status: ProjectStatus) => void;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null });
    try {
      const projects = await api.listProjects();
      set({ projects, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  selectProject: (id: string) => {
    const project = get().projects.find((p) => p.id === id) || null;
    set({ currentProject: project });
  },

  createProject: async (name, gitUrl, branch = 'main') => {
    const project = await api.createProject({ name, git_url: gitUrl, branch });
    set((s) => ({ projects: [project, ...s.projects] }));
    return project;
  },

  deleteProject: async (id) => {
    await api.deleteProject(id);
    set((s) => ({
      projects: s.projects.filter((p) => p.id !== id),
      currentProject: s.currentProject?.id === id ? null : s.currentProject,
    }));
  },

  updateProjectStatus: (id, status) => {
    set((s) => ({
      projects: s.projects.map((p) => (p.id === id ? { ...p, status } : p)),
      currentProject: s.currentProject?.id === id ? { ...s.currentProject, status } : s.currentProject,
    }));
  },
}));
