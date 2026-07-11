# AI Code Analysis Platform

AI 驱动的代码分析平台，支持 Java 仓库的静态解析、调用链图谱构建、模块依赖分析以及基于 Claude Agent 的智能代码问答。

## 功能特性

- **Git 仓库管理** — 克隆项目、自动检测语言与框架
- **AST 静态解析** — 基于 Tree-sitter 解析 Java 源码，提取类、方法、字段等符号
- **调用链图谱** — 自动构建方法间调用关系（call graph）、实现关系（implements）、字段访问（field access）
- **模块依赖分析** — 提取文件级 import 依赖
- **React Flow 可视化** — 交互式调用链图谱，支持节点展开/折叠、点击查看源码
- **AI 智能问答** — Claude Agent 通过结构化 Tool 查询符号表和调用链，回答代码架构问题

## 系统架构

```
          React Frontend
               │
       HTTP / SSE
               │
     Python FastAPI Server
               │
   ┌───────────┼───────────┐
   │           │           │
Git Manager  Code Indexer  Claude Agent
   │           │           │
 clone仓库    AST分析      AI推理
   │           │           │
    └───────────┼───────────┘
                │
           本地代码仓库
```

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19 + TypeScript + Vite |
| 图可视化 | @xyflow/react (React Flow) + dagre 布局 |
| 状态管理 | Zustand |
| 后端 | Python 3.12+ / FastAPI |
| AST 解析 | Tree-sitter (tree-sitter-java) |
| Git 管理 | GitPython |
| AI Agent | Anthropic Claude SDK |
| 数据库 | SQLite (aiosqlite) / PostgreSQL |
| ORM | SQLAlchemy 2.0 (async) |

## 项目结构

```
code_analysis/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 应用入口，CORS，生命周期
│   │   ├── core/
│   │   │   ├── config.py      # 环境变量与配置
│   │   │   └── exceptions.py  # 全局异常处理
│   │   ├── api/v1/            # REST API 路由
│   │   │   ├── projects.py    # 项目 CRUD
│   │   │   ├── files.py       # 文件内容查询
│   │   │   ├── symbols.py     # 符号查询
│   │   │   ├── graph.py       # 图谱数据 & 可视化
│   │   │   └── chat.py        # AI 对话 (SSE)
│   │   ├── models/            # SQLAlchemy ORM
│   │   ├── schemas/           # Pydantic 校验
│   │   ├── services/
│   │   │   ├── analyzer/      # Git 管理 & AST 解析
│   │   │   │   ├── git_manager.py
│   │   │   │   ├── tree_sitter_parser.py
│   │   │   │   └── ast_visitor.py
│   │   │   ├── indexer/       # 索引构建
│   │   │   │   ├── symbol_builder.py
│   │   │   │   ├── call_graph_builder.py
│   │   │   │   ├── field_access_builder.py
│   │   │   │   └── dependency_builder.py
│   │   │   ├── agent/         # Claude Agent
│   │   │   │   ├── claude_client.py
│   │   │   │   ├── prompt_manager.py
│   │   │   │   └── session_manager.py
│   │   │   └── analysis_service.py  # 分析编排
│   │   ├── tools/             # Agent Tool 集
│   │   │   ├── base.py        # Tool 注册机制
│   │   │   ├── graph_tools.py # find_symbol, find_callers, find_callees, get_class_methods
│   │   │   └── code_tools.py  # read_file, search_content
│   │   └── db/
│   │       ├── session.py     # 数据库连接
│   │       └── init_db.py     # 建表
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ProjectPage.tsx   # 项目管理
│   │   │   ├── AnalysisPage.tsx  # 图谱分析
│   │   │   └── ChatPage.tsx      # AI 对话
│   │   ├── components/
│   │   │   ├── FileTree/         # 文件树
│   │   │   ├── CodeViewer/       # 代码查看器
│   │   │   ├── Graph/            # React Flow 图谱
│   │   │   │   ├── ClassNode.tsx
│   │   │   │   ├── MethodNode.tsx
│   │   │   │   ├── FieldNode.tsx
│   │   │   │   ├── CallEdge.tsx
│   │   │   │   └── layout.ts
│   │   │   └── ResizablePanel/   # 可调整面板
│   │   ├── store/                # Zustand 状态
│   │   ├── services/api.ts      # API 客户端
│   │   └── types/index.ts       # TypeScript 类型
│   ├── vite.config.ts
│   └── package.json
└── clone_repo.py               # Git 克隆辅助脚本
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Git

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY

# 启动服务
python -m app.main
```

后端默认运行在 `http://localhost:8001`。

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 `http://localhost:5173`，已配置代理将 `/api` 请求转发至后端。

### 生产构建

```bash
cd frontend
npm run build
```

构建产物在 `frontend/dist/`。

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/projects/` | 项目列表 |
| POST | `/api/v1/projects/` | 创建项目（触发分析） |
| GET | `/api/v1/projects/{id}` | 项目详情 |
| DELETE | `/api/v1/projects/{id}` | 删除项目 |
| GET | `/api/v1/projects/{id}/files` | 项目文件列表 |
| GET | `/api/v1/symbols/` | 符号查询 |
| GET | `/api/v1/graph/visualization/{project_id}` | 图谱可视化数据 |
| GET | `/api/v1/graph/full-chain/{project_id}/{symbol_id}` | 完整调用链 |
| POST | `/api/v1/chat/{project_id}` | AI 对话（SSE 流式） |
| GET | `/api/v1/files/{id}/content` | 文件内容 |

## AI Agent Tool 列表

Claude Agent 不直接读取代码仓库，而是通过结构化 Tool 查询已构建的索引：

| Tool | 说明 |
|------|------|
| `find_symbol` | 按名称/类型查询符号 |
| `find_callers` | 查找谁调用了指定符号 |
| `find_callees` | 查找指定符号调用了谁 |
| `get_class_methods` | 获取类的所有方法 |
| `read_file` | 读取源码文件内容 |
| `search_content` | 全文搜索代码关键词 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | API 基础 URL |
| `ANTHROPIC_MODEL` | `astron-code-latest` | 使用的模型 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./code_analysis.db` | 数据库连接 |
| `WORKSPACE_DIR` | `workspace` | Git 仓库克隆目录 |
| `SERVER_PORT` | `8001` | 后端端口 |
| `DEBUG` | `true` | 调试模式 |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | CORS 允许来源 |

## License

MIT
