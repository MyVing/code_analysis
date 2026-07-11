import { create } from 'zustand';
import type { ChatMessage } from '@/types';
import { api } from '@/services/api';

interface ChatStore {
  messages: ChatMessage[];
  sessionId: string | null;
  projectId: string | null;
  loading: boolean;

  setProject: (projectId: string) => void;
  sendMessage: (content: string) => Promise<void>;
  clear: () => void;
  addMessage: (msg: ChatMessage) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: null,
  projectId: null,
  loading: false,

  setProject: (projectId) => {
    const current = get().projectId;
    if (current !== projectId) {
      set({ projectId, messages: [], sessionId: null });
    }
  },

  sendMessage: async (content) => {
    const { projectId, sessionId } = get();
    if (!projectId || !content.trim()) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: Date.now(),
    };
    set((s) => ({ messages: [...s.messages, userMsg], loading: true }));

    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    };
    set((s) => ({ messages: [...s.messages, assistantMsg] }));

    try {
      const res = await api.chatStream(projectId, content, sessionId || undefined);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let newSessionId = sessionId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // next line will have data
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              const event = lines[lines.indexOf(line) - 1]?.startsWith('event: ')
                ? lines[lines.indexOf(line) - 1].slice(7).trim()
                : '';

              if (event === 'text') {
                set((s) => ({
                  messages: s.messages.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + (data.content || '') }
                      : m,
                  ),
                }));
              } else if (event === 'tool_call') {
                const toolMsg: ChatMessage = {
                  id: `${assistantId}-tool-${Date.now()}`,
                  role: 'tool_call',
                  content: `Calling ${data.tool}(${JSON.stringify(data.args)})`,
                  timestamp: Date.now(),
                  toolName: data.tool,
                  toolArgs: data.args,
                };
                set((s) => ({ messages: [...s.messages, toolMsg] }));
              } else if (event === 'tool_result') {
                const resultMsg: ChatMessage = {
                  id: `${assistantId}-result-${Date.now()}`,
                  role: 'tool_result',
                  content: JSON.stringify(data.result, null, 2),
                  timestamp: Date.now(),
                  toolName: data.tool,
                };
                set((s) => ({ messages: [...s.messages, resultMsg] }));
              } else if (event === 'done') {
                if (data.session_id) {
                  newSessionId = data.session_id;
                }
              } else if (event === 'error') {
                set((s) => ({
                  messages: s.messages.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + `\n\nError: ${data.message}`, isStreaming: false }
                      : m,
                  ),
                }));
              }
            } catch {
              // skip malformed JSON
            }
          }
        }
      }

      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m,
        ),
        sessionId: newSessionId,
        loading: false,
      }));
    } catch (e) {
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Error: ${(e as Error).message}`, isStreaming: false }
            : m,
        ),
        loading: false,
      }));
    }
  },

  clear: () => set({ messages: [], sessionId: null }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
}));
