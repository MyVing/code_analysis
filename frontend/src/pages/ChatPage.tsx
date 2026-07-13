import { useState, useRef, useEffect } from 'react';import { useSearchParams, useNavigate } from 'react-router';
import { useProjectStore } from '@/store/projectStore';
import { useChatStore } from '@/store/chatStore';
import type { ChatMessage } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';
import './ChatPage.css';

const QUICK_ACTIONS = [
  {
    icon: '🔗',
    title: '链路分析',
    description: '追踪方法的完整调用链路',
    prompt: '分析 [类名] 的完整调用链路',
  },
  {
    icon: '🔍',
    title: '调用者查找',
    description: '查找谁调用了指定方法',
    prompt: '谁调用了 [方法名]？',
  },
  {
    icon: '📞',
    title: '被调用者查找',
    description: '查找指定类调用了哪些方法',
    prompt: '[类名] 调用了哪些方法？',
  },
  {
    icon: '🏗️',
    title: '类结构分析',
    description: '列出类的所有方法和签名',
    prompt: '分析 [类名] 的结构，列出所有方法',
  },
  {
    icon: '🔎',
    title: '代码搜索',
    description: '搜索代码中包含关键词的位置',
    prompt: '搜索代码中包含 [关键词] 的位置',
  },
  {
    icon: '📄',
    title: '代码阅读',
    description: '读取指定文件的源码',
    prompt: '读取 [文件路径] 的源码',
  },
];

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

  const handleQuickAction = (prompt: string) => {
    setInput(prompt);
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
            <p className="chat-empty-title">选择一个功能开始分析</p>
            <div className="quick-actions">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.title}
                  className="quick-action-card"
                  onClick={() => handleQuickAction(action.prompt)}
                >
                  <span className="quick-action-icon">{action.icon}</span>
                  <span className="quick-action-title">{action.title}</span>
                  <span className="quick-action-desc">{action.description}</span>
                </button>
              ))}
            </div>
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
  if (msg.role === 'thinking') {
    return (
      <div className="chat-thinking">
        <div className="thinking-spinner" />
        <span className="thinking-text">{msg.content}</span>
        {msg.toolSteps && msg.toolSteps.length > 0 && (
          <div className="thinking-steps">
            {msg.toolSteps.map((step, i) => {
              const args = step.args;
              const label = args?.name || args?.symbol_name || args?.class_name || args?.file_path || args?.query || step.tool;
              return (
                <span key={i} className="thinking-step-tag" title={JSON.stringify(step.args, null, 2)}>
                  {step.tool}: {typeof label === 'string' && label.length > 20 ? label.slice(0, 20) + '...' : label}
                </span>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`chat-bubble chat-${msg.role}`}>
      <div className="bubble-content">
        {msg.role === 'assistant' ? (
          msg.isStreaming ? (
            <pre className="streaming-raw">{msg.content}</pre>
          ) : (
            <ReactMarkdown key="final" remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {msg.content}
            </ReactMarkdown>
          )
        ) : (
          msg.content
        )}
        {msg.isStreaming && <span className="cursor-blink">▊</span>}
      </div>
    </div>
  );
}
