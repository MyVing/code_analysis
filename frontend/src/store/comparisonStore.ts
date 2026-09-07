import { create } from 'zustand';
import { api } from '@/services/api';
import type { ChangedFile, CommitDiff, FileDiff, GitCommit } from '@/types';

interface ComparisonState {
  commits: GitCommit[]; baseCommit: string; headCommit: string; diff: CommitDiff | null; selectedFile: ChangedFile | null; fileDiff: FileDiff | null; loading: boolean; error: string | null;
  fetchCommits: (projectId: string) => Promise<void>;
  setBaseCommit: (value: string) => void; setHeadCommit: (value: string) => void;
  compare: (projectId: string) => Promise<void>; selectFile: (projectId: string, file: ChangedFile) => Promise<void>;
}

export const useComparisonStore = create<ComparisonState>((set, get) => ({
  commits: [], baseCommit: '', headCommit: '', diff: null, selectedFile: null, fileDiff: null, loading: false, error: null,
  fetchCommits: async (projectId) => { set({ loading: true, error: null }); try { const commits = await api.listCommits(projectId); set({ commits, headCommit: commits[0]?.sha || '', baseCommit: commits[1]?.sha || '', loading: false }); } catch (e) { set({ error: (e as Error).message, loading: false }); } },
  setBaseCommit: (baseCommit) => set({ baseCommit }), setHeadCommit: (headCommit) => set({ headCommit }),
  compare: async (projectId) => { const { baseCommit, headCommit } = get(); if (!baseCommit || !headCommit || baseCommit === headCommit) { set({ error: '请选择两个不同的 commit' }); return; } set({ loading: true, error: null }); try { set({ diff: await api.compareCommits(projectId, baseCommit, headCommit), loading: false }); } catch (e) { set({ error: (e as Error).message, loading: false }); } },
  selectFile: async (projectId, selectedFile) => { const { baseCommit, headCommit } = get(); const path = selectedFile.new_path || selectedFile.old_path; if (!path) return; set({ selectedFile, loading: true, error: null }); try { set({ fileDiff: await api.getFileDiff(projectId, baseCommit, headCommit, path), loading: false }); } catch (e) { set({ error: (e as Error).message, loading: false }); } },
}));
