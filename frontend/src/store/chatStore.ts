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
    const thinkingId = `${assistantId}-thinking`;
    const thinkingMsg: ChatMessage = {
      id: thinkingId,
      role: 'thinking',
      content: '',
      timestamp: Date.now(),
      toolSteps: [],
    };
    set((s) => ({ messages: [...s.messages, assistantMsg, thinkingMsg] }));

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
      let currentEvent = ''; // Track current SSE event type
      let currentData = ''; // Accumulate data lines for multi-line data

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep the last (potentially incomplete) line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            // Accumulate data content (SSE allows multiple data: lines per event)
            currentData += (currentData ? '\n' : '') + line.slice(6);
          } else if (trimmed === '') {
            // Empty line = SSE event separator, process accumulated event
            if (currentEvent && currentData) {
              try {
                const data = JSON.parse(currentData);
                const event = currentEvent;

                if (event === 'thinking') {
                  set((s) => ({
                    messages: s.messages.map((m) =>
                      m.id === thinkingId
                        ? { ...m, content: '正在分析...' }
                        : m,
                    ),
                  }));
                } else if (event === 'tool_call') {
                  set((s) => ({
                    messages: s.messages.map((m) =>
                      m.id === thinkingId
                        ? {
                            ...m,
                            content: `正在调用工具分析 (${(m.toolSteps?.length || 0) + 1}步)...`,
                            toolSteps: [...(m.toolSteps || []), { tool: data.tool, args: data.args }],
                          }
                        : m,
                    ),
                  }));
                } else if (event === 'tool_result') {
                  // Tool result is absorbed into thinking, no separate message
                } else if (event === 'report_start') {
                  // AI is about to stream the final report
                  // Clear thinking message only; assistant content stays as-is (empty initially)
                  set((s) => ({
                    messages: s.messages
                      .filter((m) => m.id !== thinkingId),
                  }));
                } else if (event === 'text') {
                  set((s) => ({
                    messages: s.messages.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: m.content + (data.content || '') }
                        : m,
                    ),
                  }));
                } else if (event === 'done') {
                  if (data.session_id) {
                    newSessionId = data.session_id;
                  }
                  // Remove thinking message and mark assistant as complete
                  set((s) => ({
                    messages: s.messages
                      .filter((m) => m.id !== thinkingId)
                      .map((m) =>
                        m.id === assistantId
                          ? { ...m, isStreaming: false }
                          : m,
                      ),
                    loading: false,
                  }));
                  });
                } else if (event === 'error') {
                  set((s) => ({
                    messages: s.messages
                      .filter((m) => m.id !== thinkingId)
                      .map((m) =>
                        m.id === assistantId
                          ? { ...m, content: m.content + `\n\nError: ${data.message}`, isStreaming: false }
                          : m,
                      ),
                    loading: false,
                  }));
                }
              } catch {
                // skip malformed JSON
              }
            }
            // Reset for next event
            currentEvent = '';
            currentData = '';
          }
          // Ignore comment lines (starting with ':') and other unknown lines
        }
      }

      // If stream ended without 'done' event, still clean up thinking
      set((s) => ({
        messages: s.messages
          .filter((m) => m.id !== thinkingId)
          .map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m,
          ),
        sessionId: newSessionId,
        loading: false,
      }));
    } catch (e) {
      set((s) => ({
        messages: s.messages
          .filter((m) => m.id !== thinkingId)
          .map((m) =>
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
