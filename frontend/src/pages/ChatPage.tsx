import { useState, useRef, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { useProjectStore } from '@/store/projectStore';
import { useChatStore } from '@/store/chatStore';
import type { ChatMessage } from '@/types';
import './ChatPage.css';

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { currentProject, projects, selectProject } = useProjectStore();
  const { messages, loading, sendMessage, setProject, sessionId } = useChatStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Handle URL params for graph linkage
  useEffect(() => {
    const projectId = searchParams.get('projectId');
    const question = searchParams.get('question');
    if (projectId && (!currentProject || currentProject.id !== projectId)) {
      const p = projects.find((pr) => pr.id === projectId);
      if (p) selectProject(p.id);
    }
  }, [searchParams, projects, currentProject, selectProject]);

  useEffect(() => {
    if (currentProject) {
      setProject(currentProject.id);
    }
  }, [currentProject, setProject]);

  // Auto-send question from URL
  useEffect(() => {
    const question = searchParams.get('question');
    if (question && currentProject && !loading) {
      // Clear the URL param after sending
      navigate('/chat', { replace: true });
      sendMessage(question);
    }
  }, [searchParams, currentProject]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || loading) return;
    sendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h1>AI Chat</h1>
        {currentProject && (
          <span className="chat-project-badge">{currentProject.name}</span>
        )}
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p>Ask questions about your codebase.</p>
            <p className="chat-hint">e.g. "Who calls UserService?" or "Explain the authentication flow"</p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatBubble key={msg.id} msg={msg} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={currentProject ? `Ask about ${currentProject.name}...` : 'Select a project first...'}
          rows={2}
          disabled={!currentProject || loading}
        />
        <button
          className="btn btn-primary chat-send"
          onClick={handleSend}
          disabled={!input.trim() || loading || !currentProject}
        >
          {loading ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'tool_call') {
    return (
      <div className="chat-tool-call">
        <span className="tool-icon">🔧</span>
        <span className="tool-name">{msg.toolName}</span>
        {msg.toolArgs && (
          <code className="tool-args">{JSON.stringify(msg.toolArgs)}</code>
        )}
      </div>
    );
  }

  if (msg.role === 'tool_result') {
    return (
      <div className="chat-tool-result">
        <details>
          <summary>
            <span className="tool-icon">📋</span>
            Result from {msg.toolName}
          </summary>
          <pre className="tool-result-content">{msg.content}</pre>
        </details>
      </div>
    );
  }

  return (
    <div className={`chat-bubble chat-${msg.role}`}>
      <div className="bubble-content">
        {msg.content}
        {msg.isStreaming && <span className="cursor-blink">▊</span>}
      </div>
    </div>
  );
}
