import { useState, useRef, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { useProjectStore } from '@/store/projectStore';
import { useChatStore } from '@/store/chatStore';
import { usePromptTemplateStore } from '@/store/promptTemplateStore';
import type { ChatMessage, PromptTemplate } from '@/types';
import { api } from '@/services/api';
import StructuredResultView from '@/components/StructuredResult/StructuredResult';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import './ChatPage.css';

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { currentProject, projects, selectProject } = useProjectStore();
  const { messages, loading, sendMessage, setProject, sessionId } = useChatStore();
  const { templates, fetchTemplates } = usePromptTemplateStore();
  const [input, setInput] = useState('');
  const [activeTemplate, setActiveTemplate] = useState<PromptTemplate | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
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

  // Load prompt templates
  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  // Auto-send question from URL
  useEffect(() => {
    const question = searchParams.get('question');
    if (question && currentProject && !loading) {
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

  const handleTemplateClick = (template: PromptTemplate) => {
    if (template.parameters.length === 0) {
      sendMessage(template.prompt_template);
    } else {
      setActiveTemplate(template);
    }
  };

  const handleFormSubmit = async (params: Record<string, string>, customSchema?: Record<string, any>) => {
    if (!activeTemplate) return;
    let prompt = activeTemplate.prompt_template;
    for (const [key, value] of Object.entries(params)) {
      prompt = prompt.replace(`{${key}}`, value);
    }
    const schema = customSchema || activeTemplate.output_schema;
    if (schema) {
      sendMessage(prompt, activeTemplate.id, params, schema);
    } else {
      sendMessage(prompt);
    }
    setActiveTemplate(null);
  };

  // Group templates by category
  const groupedTemplates = templates.reduce<Record<string, PromptTemplate[]>>((acc, t) => {
    const cat = t.category || 'general';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {});

  const categoryLabels: Record<string, string> = {
    call_chain: '调用链分析',
    structure: '结构分析',
    search: '代码搜索',
    general: '通用',
  };

  return (
    <div className="chat-page">
      {/* Left sidebar: prompt templates */}
      <div className={`chat-sidebar ${sidebarCollapsed ? 'chat-sidebar-collapsed' : ''}`}>
        <div className="chat-sidebar-header">
          {!sidebarCollapsed && <span className="chat-sidebar-title">提示词模板</span>}
          <button
            className="chat-sidebar-toggle"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            {sidebarCollapsed ? '»' : '«'}
          </button>
        </div>
        {!sidebarCollapsed && (
          <div className="chat-sidebar-body">
            {Object.entries(groupedTemplates).map(([category, items]) => (
              <div key={category} className="template-group">
                <div className="template-group-label">
                  {categoryLabels[category] || category}
                </div>
                {items.map((template) => (
                  <button
                    key={template.id}
                    className="template-item"
                    onClick={() => handleTemplateClick(template)}
                    title={template.description}
                  >
                    <span className="template-item-icon">{template.icon}</span>
                    <span className="template-item-name">{template.name}</span>
                    {template.output_schema && <span className="template-item-badge">JSON</span>}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right: chat area */}
      <div className="chat-main">
        <div className="chat-header">
          <h1>AI Chat</h1>
          {currentProject && (
            <span className="chat-project-badge">{currentProject.name}</span>
          )}
        </div>

        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <p className="chat-empty-title">从左侧选择功能开始分析</p>
              <p className="chat-empty-hint">或直接在下方输入问题</p>
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

      {activeTemplate && (
        <PromptFormModal
          template={activeTemplate}
          onSubmit={handleFormSubmit}
          onClose={() => setActiveTemplate(null)}
        />
      )}
    </div>
  );
}

function PromptFormModal({
  template,
  onSubmit,
  onClose,
}: {
  template: PromptTemplate;
  onSubmit: (params: Record<string, string>, customSchema?: Record<string, any>) => void;
  onClose: () => void;
}) {
  const [params, setParams] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const p of template.parameters) {
      initial[p.key] = '';
    }
    return initial;
  });

  const defaultSchemaStr = template.output_schema
    ? JSON.stringify(template.output_schema, null, 2)
    : '';
  const [schemaText, setSchemaText] = useState(defaultSchemaStr);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [showSchema, setShowSchema] = useState(!!template.output_schema);

  const handleChange = (key: string, value: string) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const parseSchema = (): Record<string, any> | undefined => {
    if (!schemaText.trim()) return undefined;
    try {
      const parsed = JSON.parse(schemaText);
      setSchemaError(null);
      return parsed;
    } catch (e) {
      setSchemaError((e as Error).message);
      return undefined;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const hasEmpty = template.parameters
      .filter((p) => p.required)
      .some((p) => !params[p.key]?.trim());
    if (hasEmpty) return;

    const customSchema = parseSchema();
    if (schemaText.trim() && !customSchema) return; // JSON parse error

    onSubmit(params, customSchema);
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content modal-content-wide">
        <div className="modal-header">
          <span className="modal-icon">{template.icon}</span>
          <h2 className="modal-title">{template.name}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <p className="modal-desc">{template.description}</p>
        <form onSubmit={handleSubmit}>
          <div className="modal-form">
            {template.parameters.map((param) => (
              <div key={param.key} className="form-field">
                <label className="form-label">
                  {param.label}
                  {param.required && <span className="form-required">*</span>}
                </label>
                {param.type === 'select' && param.options ? (
                  <select
                    className="form-select"
                    value={params[param.key] || ''}
                    onChange={(e) => handleChange(param.key, e.target.value)}
                  >
                    <option value="">请选择...</option>
                    {param.options.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="form-input"
                    type="text"
                    value={params[param.key] || ''}
                    onChange={(e) => handleChange(param.key, e.target.value)}
                    placeholder={param.placeholder || `输入${param.label}`}
                    autoFocus={template.parameters[0]?.key === param.key}
                  />
                )}
              </div>
            ))}

            {/* Output Schema Editor */}
            <div className="form-field">
              <div className="form-label-row">
                <label className="form-label">返回格式 (JSON Schema)</label>
                <button
                  type="button"
                  className="schema-toggle-btn"
                  onClick={() => setShowSchema(!showSchema)}
                >
                  {showSchema ? '收起' : '自定义'}
                </button>
              </div>
              {showSchema && (
                <>
                  <textarea
                    className={`form-textarea ${schemaError ? 'form-textarea-error' : ''}`}
                    value={schemaText}
                    onChange={(e) => {
                      setSchemaText(e.target.value);
                      if (schemaError) setSchemaError(null);
                    }}
                    placeholder='定义 AI 返回的 JSON 格式，例如：&#10;{&#10;  "type": "object",&#10;  "properties": {&#10;    "方法名": { "type": "string" },&#10;    "上游": { "type": "array", "items": { "type": "string" } }&#10;  }&#10;}'
                    rows={10}
                  />
                  {schemaError && <span className="form-error">{schemaError}</span>}
                </>
              )}
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary">开始分析</button>
          </div>
        </form>
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
          msg.structuredData ? (
            <StructuredResultView data={msg.structuredData} schema={msg.outputSchema} />
          ) : msg.isStreaming ? (
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
