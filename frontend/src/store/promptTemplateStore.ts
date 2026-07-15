import { create } from 'zustand';
import type { PromptTemplate } from '@/types';
import { api } from '@/services/api';

interface PromptTemplateStore {
  templates: PromptTemplate[];
  loading: boolean;
  error: string | null;

  fetchTemplates: () => Promise<void>;
  createTemplate: (data: Partial<PromptTemplate> & { name: string; prompt_template: string }) => Promise<PromptTemplate>;
  updateTemplate: (id: string, data: Partial<PromptTemplate>) => Promise<PromptTemplate>;
  deleteTemplate: (id: string) => Promise<void>;
}

export const usePromptTemplateStore = create<PromptTemplateStore>((set, get) => ({
  templates: [],
  loading: false,
  error: null,

  fetchTemplates: async () => {
    set({ loading: true, error: null });
    try {
      const templates = await api.listPromptTemplates();
      set({ templates, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createTemplate: async (data) => {
    const template = await api.createPromptTemplate(data);
    set((s) => ({ templates: [...s.templates, template] }));
    return template;
  },

  updateTemplate: async (id, data) => {
    const template = await api.updatePromptTemplate(id, data);
    set((s) => ({
      templates: s.templates.map((t) => (t.id === id ? template : t)),
    }));
    return template;
  },

  deleteTemplate: async (id) => {
    await api.deletePromptTemplate(id);
    set((s) => ({ templates: s.templates.filter((t) => t.id !== id) }));
  },
}));
