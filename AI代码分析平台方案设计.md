# AI 代码分析平台方案设计

## 一、总体技术选型

-   前端：React + TypeScript
-   UI：Tailwind CSS + shadcn/ui
-   图形展示：React Flow
-   后端：Python + FastAPI
-   AI Agent：Claude Agent SDK
-   Git 管理：GitPython
-   AST 分析：Tree-sitter
-   数据库：SQLite（开发）/ PostgreSQL（生产）
-   实时通信：WebSocket

------------------------------------------------------------------------

## 二、系统整体架构

``` text
                React
                  │
        WebSocket / HTTP
                  │
      Python FastAPI Server
                  │
    ┌─────────────┼─────────────┐
    │             │             │
 Git Manager   Code Indexer   Claude Agent
    │             │             │
 clone仓库      AST分析        AI推理
    │             │             │
     └─────────────┼─────────────┘
                   │
              本地代码仓库
```

------------------------------------------------------------------------

## 三、前端方案

### 技术栈

-   React
-   TypeScript
-   Vite
-   React Flow

### 页面结构

``` text
src
├── pages
│   ├── Project
│   ├── Analysis
│   └── Chat
├── components
│   ├── FileTree
│   ├── CodeViewer
│   ├── Graph
│   ├── AIChat
│   └── Timeline
├── hooks
├── services
├── store
└── utils
```

### 功能

-   项目管理
-   文件树浏览
-   React Flow 调用链可视化
-   AI 对话分析
-   节点点击查看源码
-   调用链展开/折叠

------------------------------------------------------------------------

## 四、后端架构

### 流程

``` text
Git Clone
    ↓
扫描项目
    ↓
AST解析
    ↓
建立Symbol Table
    ↓
建立Call Graph
    ↓
建立Dependency Graph
    ↓
Claude Agent推理
```

### 分层

``` text
backend/
├── api/
├── agent/
├── analyzer/
│   ├── git_manager.py
│   ├── parser.py
│   ├── symbol_index.py
│   ├── call_graph.py
│   ├── dependency_graph.py
│   └── project_detector.py
├── tools/
│   ├── find_symbol.py
│   ├── find_callers.py
│   ├── find_callees.py
│   ├── search_file.py
│   └── read_code.py
└── workspace/
```

------------------------------------------------------------------------

## 五、Git 仓库管理

Workspace 示例：

``` text
workspace/
    spring-ai/
    demo/
    project/
```

项目元数据：

``` json
{
  "name": "",
  "language": "",
  "framework": "",
  "branch": "",
  "commit": ""
}
```

------------------------------------------------------------------------

## 六、代码分析引擎

### 建立索引

``` text
Project
   ↓
Tree-sitter
   ↓
AST
   ↓
Class
Method
Import
Variable
Decorator
Call
Reference
```

### 调用链

``` text
Controller
    ↓
Service
    ↓
Repository
    ↓
Database
```

### 模块依赖

``` text
OrderService
    ↓
Redis
    ↓
MQ
    ↓
Payment
```

------------------------------------------------------------------------

## 七、AI Agent

Agent 不直接读取整个仓库，而是通过 Tool 调用。

### Tool

-   find_class()
-   find_method()
-   find_symbol()
-   find_callers()
-   find_callees()
-   read_file()
-   search_symbol()
-   grep()
-   run_ripgrep()

工作流程：

``` text
用户问题
    ↓
Claude Agent
    ↓
Tool 查询
    ↓
读取分析结果
    ↓
生成回答
```

------------------------------------------------------------------------

## 八、开发阶段

### 第一阶段

-   Clone 项目
-   AST 解析
-   建立索引
-   生成 Graph

### 第二阶段

-   Claude Agent
-   Tool 调用
-   AI 推理

### 第三阶段

-   React Flow 可视化
-   AI 分析
-   调用链浏览
-   节点查看源码

------------------------------------------------------------------------

## 九、最终目标

打造类似 Cursor、Sourcegraph、OpenHands 的 AI 代码分析平台，实现：

-   代码调用链分析
-   模块依赖分析
-   AI 问答
-   项目结构分析
-   React Flow 图形展示
-   Claude Agent 智能分析



以下是为您深度完善和扩展的《AI 代码分析平台方案设计》。内容按照您的需求进行了专业级的细化，适合直接作为技术架构文档或开发指导手册。

---

# AI 代码分析平台方案设计（进阶版）

## 一、 系统总体架构图（规范分层架构）

采用标准的五层架构设计，明确各层边界与职责：

```text
┌─────────────────────────────────────────────────────────────────┐
│                         表现层                      │
│   React + TypeScript + Tailwind + shadcn/ui + React Flow        │
├─────────────────────────────────────────────────────────────────┤
│                       接入层                    │
│          FastAPI Router (RESTful API + WebSocket Server)         │
├──────────────────┬──────────────────┬───────────────────────────┤
│                  │                  │                           │
│   业务逻辑层      │   AI 智能层       │       工具层       │
│  (Analyzer/Index)│  (Claude Agent)  │  (Tools for Agent)        │
│                  │                  │                           │
├──────────────────┴──────────────────┴───────────────────────────┤
│                       数据持久层                  │
│          SQLite (Dev) / PostgreSQL (Prod) + File System         │
├─────────────────────────────────────────────────────────────────┤
│                       基础设施层                │
│         GitPython (仓库管理) + Tree-sitter (AST解析)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、 核心模块设计

### 1. Analyzer 模块（分析器）
- **职责**：负责代码的静态解析，不涉及业务逻辑推断。
- **核心类**：
  - `GitManager`：拉取代码、切换分支、获取 commit log。
  - `TreeSitterParser`：根据语言加载对应的 `.so` 动态库，生成原始 AST。
  - `ASTVisitor`：遍历 AST，提取节点信息。

### 2. Index 模块（索引器）
- **职责**：将 Analyzer 提取的原始数据构建为可查询的图结构或关系型数据。
- **核心类**：
  - `SymbolTableBuilder`：构建类、方法、变量的符号表，处理作用域。
  - `CallGraphBuilder`：建立方法间的调用关系（谁调用了谁）。
  - `DependencyGraphBuilder`：建立文件/模块级别的导入依赖关系。

### 3. Tool 模块（Agent 工具集）
- **职责**：作为 Claude Agent 的“手和眼”，屏蔽底层 SQL 查询和文件 IO 细节。
- **设计原则**：每个 Tool 的入参和出参必须高度结构化（JSON），且描述需极其精准，以降低 Agent 幻觉。

### 4. Agent 模块（智能体）
- **职责**：管理 Claude 的生命周期、上下文窗口和 Tool 调用循环。
- **核心类**：
  - `AgentSession`：维护单个用户的对话历史。
  - `PromptManager`：动态拼接 System Prompt（注入当前项目的语言、框架、结构概要）。

### 5. Frontend 模块（前端展示）
- **职责**：状态管理、图形渲染、实时通信。
- **核心机制**：使用 Zustand 维护全局 `ProjectStore` 和 `GraphStore`，通过 WebSocket 订阅分析进度。

---

## 三、 数据库设计

采用关系型数据库适配图数据的邻接表模型设计：

### 1. `projects` (项目表)
| 字段     | 类型    | 说明                                     |
| :------- | :------ | :--------------------------------------- |
| id       | UUID    | 主键                                     |
| name     | VARCHAR | 项目名                                   |
| git_url  | VARCHAR | git 地址                                 |
| language | VARCHAR | 主语言                                   |
| branch   | VARCHAR | 当前分析分支                             |
| status   | ENUM    | pending, parsing, indexing, ready, error |

### 2. `files` (文件表)
| 字段         | 类型    | 说明                           |
| :----------- | :------ | :----------------------------- |
| id           | UUID    | 主键                           |
| project_id   | UUID    | 外键                           |
| file_path    | VARCHAR | 相对路径 (如: `src/main.java`) |
| language     | VARCHAR | 具体语言                       |
| content_hash | VARCHAR | 内容 MD5，用于增量更新         |

### 3. `symbols` (符号表)
| 字段       | 类型    | 说明                                         |
| :--------- | :------ | :------------------------------------------- |
| id         | UUID    | 主键                                         |
| file_id    | UUID    | 外键                                         |
| parent_id  | UUID    | 父符号 ID (如方法的父级是类，为空则顶层)     |
| name       | VARCHAR | 符号名                                       |
| kind       | ENUM    | class, method, function, variable, interface |
| signature  | TEXT    | 方法签名 (如 `getUser(id: string): User`)    |
| start_line | INT     | 起始行                                       |
| end_line   | INT     | 结束行                                       |

### 4. `call_graph` (调用链图表)
| 字段        | 类型 | 说明               |
| :---------- | :--- | :----------------- |
| id          | UUID | 主键               |
| project_id  | UUID | 外键               |
| caller_id   | UUID | 调用者 Symbol ID   |
| callee_id   | UUID | 被调用者 Symbol ID |
| file_id     | UUID | 发生调用的文件 ID  |
| line_number | INT  | 发生调用的具体行号 |

### 5. `imports` (依赖图表)
| 字段           | 类型    | 说明               |
| :------------- | :------ | :----------------- |
| id             | UUID    | 主键               |
| source_file_id | UUID    | 发起 import 的文件 |
| target_module  | VARCHAR | 被导入的模块路径   |

---

## 四、 AST 索引设计

为了兼顾查询性能与存储，采用**扁平化+作用域链**的设计，不存储完整 AST 树：

1. **降维存储**：只将有语义价值的节点（Class, Method, Func, Interface, Import）存入 `symbols` 表，过滤掉括号、操作符等语法噪声。
2. **作用域解析**：
   - 通过 `parent_id` 建立树状作用域。
   - 例如：`UserService.findAll()` 的 `parent_id` 指向 `UserService` 的 Symbol ID。
3. **引用解析**：
   - 在 `call_graph` 表中记录调用动作。
   - 对于跨文件调用，Index 模块在构建时需要进行一次轻量级的“名字解析”，将代码中的 `xxx.method()` 绑定到具体的 `symbols.id`。

---

## 五、 Tool 调用流程图

```text
[用户提问]: "找到 UserService 的所有调用者"
       │
       ▼
[Agent 控制器] ────> 组装 Prompt + Tool Definitions
       │
       ▼
[Claude API] (思考后决定调用 tool: find_callers)
       │
       ▼ (返回 Tool Call: {name: "find_callers", args: {symbol_name: "UserService"}})
       │
[Tool 执行引擎] 
       │
       ├─1. 查询 Symbol 表: SELECT id FROM symbols WHERE name='UserService'
       │
       ├─2. 查询 CallGraph 表: SELECT caller_id FROM call_graph WHERE callee_id=<id>
       │
       ├─3. 补全信息: JOIN symbols 获取 caller 的文件路径和行号
       │
       ▼ (返回 Tool Result: JSON 格式的调用列表)
       │
[Claude API] (接收到结果，组织自然语言回答)
       │
       ▼
[返回给前端展示]
```

---

## 六、 Claude Agent 工作流程

1. **System Prompt 注入**：
   ```text
   你是一个高级代码架构师。当前分析的项目是 {project_name}，主要使用 {language} 和 {framework}。
   项目包含 {file_count} 个文件，{symbol_count} 个符号。
   你可以使用提供的工具来查询符号表、调用链和读取源码。不要猜测代码内容，必须通过工具获取。
   ```
2. **用户输入处理**：将用户问题转为 Claude 的 `user` message。
3. **Agentic Loop（循环执行）**：
   - 调用 Claude API。
   - 如果返回 `stop_reason: "tool_use"`，解析工具名和参数，执行本地 Python Tool 函数。
   - 将工具执行结果作为 `tool_result` message 追加到上下文，再次调用 Claude。
   - 如果返回 `stop_reason: "end_turn"`，中断循环，将文本返回给前端。
4. **上下文裁剪**：如果对话历史超过 Token 限制，使用摘要策略压缩早期的 Tool Result。

---

## 七、 React Flow 数据结构设计

定义严格的 TypeScript 类型，确保节点和边能正确渲染：

```typescript
// 1. 节点类型枚举
type NodeType = 'classNode' | 'methodNode' | 'fileNode' | 'externalNode';

// 2. 自定义 Node Data
interface CustomNodeData {
  label: string;
  type: NodeType;
  filePath: string;
  startLine: number;
  endLine: number;
  language: string;
  // 样式控制
  color?: string; // 例如: Controller绿, Service蓝, Repository紫
}

// 3. React Flow Node 定义
type CustomNode = Node<CustomNodeData>;

// 4. 边类型枚举
type EdgeType = 'call' | 'inherit' | 'import' | 'implement';

// 5. 自定义 Edge Data
interface CustomEdgeData {
  label?: string;
  type: EdgeType;
  lineNumber?: number; // 发生调用的行号
}

// 6. React Flow Edge 定义
type CustomEdge = Edge<CustomEdgeData>;

// 7. 前端 Store 示例
interface GraphStore {
  nodes: CustomNode[];
  edges: CustomEdge[];
  selectedNode: CustomNode | null;
  onNodeClick: (node: CustomNode) => void; // 触发右侧代码高亮
  expandNode: (nodeId: string) => void;   // 展开某个类的内部方法调用
}
```

---

## 八、 WebSocket 实时分析流程

采用发布-订阅模式，前端感知后端的耗时任务进度。

**协议设计 (JSON)**：
```json
// 1. 客户端发送分析指令
{"type": "start_analysis", "project_id": "xxx"}

// 2. 服务端推送进度
{"type": "progress", "step": "cloning", "percent": 10, "message": "正在拉取 Git 仓库..."}
{"type": "progress", "step": "parsing", "percent": 40, "message": "Tree-sitter 解析中 (120/300)"}
{"type": "progress", "step": "indexing", "percent": 80, "message": "构建调用链图谱..."}

// 3. 服务端推送完成及初始数据
{
  "type": "analysis_complete", 
  "payload": {
    "stats": {"files": 300, "symbols": 4500, "edges": 12000},
    "initial_graph_nodes": [...], 
    "initial_graph_edges": [...]
  }
}

// 4. 异常处理
{"type": "error", "message": "AST 解析失败: 不支持的语法"}
```

---

## 九、 后端目录结构（完整工程）

基于 FastAPI 的企业级标准目录结构：

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app 实例，CORS，生命周期
│   ├── core/
│   │   ├── config.py           # 环境变量读取
│   │   └── exceptions.py       # 全局异常处理
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── projects.py     # 项目 CRUD 接口
│   │   │   ├── symbols.py      # 符号查询接口
│   │   │   └── graph.py        # 图谱数据接口
│   │   └── ws/
│   │       └── analysis.py     # WebSocket 分析进度推送
│   ├── models/                 # SQLAlchemy ORM 模型
│   │   ├── project.py
│   │   ├── file.py
│   │   ├── symbol.py
│   │   └── graph.py
│   ├── schemas/                # Pydantic 数据校验
│   │   ├── project.py
│   │   └── graph.py
│   ├── services/               # 核心业务逻辑层
│   │   ├── analyzer/
│   │   │   ├── git_manager.py
│   │   │   ├── tree_sitter_parser.py
│   │   │   └── ast_visitor.py
│   │   ├── indexer/
│   │   │   ├── symbol_builder.py
│   │   │   ├── call_graph_builder.py
│   │   │   └── dependency_builder.py
│   │   └── agent/
│   │       ├── claude_client.py    # Claude SDK 封装
│   │       ├── prompt_manager.py
│   │       └── session_manager.py
│   ├── tools/                  # Agent 专用工具集
│   │   ├── base.py             # Tool 基类，注册装饰器
│   │   ├── code_tools.py       # read_file, search_content
│   │   └── graph_tools.py      # find_callers, find_callees, get_class_methods
│   └── db/
│       ├── session.py          # 数据库连接池
│       └── init_db.py          # 建表逻辑
├── workspace/                  # Git 代码克隆存放地 (.gitignore)
├── tests/
├── requirements.txt
└── pyproject.toml
```

---

## 十、 MVP 开发计划 (迭代路线图)

### 🎯 第一版 (V1.0)：静态解析引擎 (预计 2 周)
**目标**：跑通“Git Clone -> AST -> 索引入库”的冷启动流程。
- [ ] 搭建 FastAPI 基础框架与 SQLite 数据库。
- [ ] 实现 `GitManager`：输入 Git URL，克隆到 `workspace`。
- [ ] 集成 Tree-sitter：实现对 Java文件的遍历。
- [ ] 实现 `SymbolBuilder`：将类、方法提取存入 `symbols` 表。
- [ ] 提供 REST API：`GET /api/v1/projects/{id}/files` 和 `GET /api/symbols?file_id=x`。
- **交付物**：可以通过 Postman 提交 Git 仓库，查询到解析出的类和方法列表。

### 🎯 第二版 (V2.0)：图谱构建与 AI 接入 (预计 2-3 周)
**目标**：建立调用关系，接入 Claude 实现自然语言查询。
- [ ] 实现 `CallGraphBuilder`：通过 AST 中的 `call_expression` 建立 `call_graph` 表。
- [ ] 封装 Agent Tool：实现 `find_symbol`、`find_callers`、`read_file`。
- [ ] 集成 Claude Agent SDK：实现 Agentic Loop。
- [ ] 实现 WebSocket 接口：将分析进度（克隆、解析、建图）实时推送到前端。
- [ ] 前端基础页：项目列表页 + 简单的文件树组件。
- **交付物**：前端可以创建项目并看到进度条，在聊天框中问“谁调用了 UserMapper”，Claude 能准确返回代码片段。

### 🎯 第三版 (V3.0)：可视化与体验优化 (预计 2 周)
**目标**：完成核心视觉交互，达到产品级 Demo 标准。
- [ ] 接入 React Flow：将 `call_graph` 数据转换为 `nodes` 和 `edges` 渲染。
- [ ] 实现交互：点击节点，右侧 CodeViewer 高亮对应源码。
- [ ] 实现图谱下钻：点击类节点，动态展开其内部方法的调用链。
- [ ] 样式美化：使用 react/ui 统一风格，不同层级节点使用不同颜色（如 Controller、Service、DAO）。
- [ ] 性能优化：大图渲染时的虚拟化或合并同类节点。
- **交付物**：完整的 MVP 演示，具备类似 Sourcegraph/Cursor 的图形化代码洞察雏形。
