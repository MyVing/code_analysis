# Git 提交对比分析功能设计方案

> 文档状态：方案设计，尚未开始实现  
> 适用项目：AI Code Analysis Platform  
> 更新时间：2026-09-06

## 1. 背景与目标

当前系统支持对一个 Git 项目进行 Java 源码解析，并生成：

- 文件索引；
- 类、方法、字段等符号信息；
- 方法调用图；
- 字段访问关系；
- import 和模块依赖关系；
- 基于分析结果的 AI 代码问答。

当前分析面向的是项目某一时刻的单个版本。项目模型只保存一个当前 commit，重跑分析时会清理原有符号和图谱数据，因此暂时无法安全地比较两个 Git 提交之间的代码变化。

本功能的目标是新增一条独立的 Git 提交对比分析链路，逐步实现：

```text
Git 文本差异
    → 文件变化
    → 类和方法变化
    → 调用关系变化
    → 影响范围分析
    → AI 变更总结、风险和测试建议
```

## 2. 功能价值

该功能不只是展示普通 `git diff`，而是将代码行级变化转换为可理解的技术变化和影响信息。

### 2.1 主要使用场景

1. **辅助 Code Review**
   - 快速了解一个提交修改了什么；
   - 识别高风险文件和核心方法；
   - 提示异常处理、公共接口和依赖变化。

2. **发布前影响评估**
   - 对比生产版本和待发布版本；
   - 识别修改的 Controller、Service、Repository 等模块；
   - 推荐需要回归测试的功能。

3. **线上问题排查**
   - 对比正常版本和异常版本；
   - 缩小可能引入问题的提交范围；
   - 查看调用链和依赖关系的变化。

4. **重构风险分析**
   - 识别公共方法签名变化；
   - 识别调用目标变更；
   - 分析修改方法的上下游调用者。

5. **项目维护和新人熟悉代码**
   - 通过两个版本理解模块演化；
   - 生成提交摘要和技术变更说明；
   - 辅助生成发布日志和 PR 描述。

## 3. 功能范围

### 3.1 第一阶段：Git Diff MVP

第一阶段只关注可靠的 Git 差异展示，不改动当前项目分析数据：

- 获取项目 commit 列表；
- 选择 base commit 和 head commit；
- 获取文件级变化；
- 支持新增、删除、修改、重命名和复制文件；
- 统计新增行数和删除行数；
- 查看单文件 patch/hunk；
- 查看旧版本和新版本文件内容；
- 支持 Java 文件筛选；
- 标识二进制文件和超大文件；
- 处理空 diff、相同 commit 和非法 commit。

### 3.2 第二阶段：结构化代码变化

对发生变化的 Java 文件分别解析 old/head 两个版本：

- 新增、删除、修改的类；
- 新增、删除、修改的方法；
- 方法签名变化；
- 方法体变化；
- 可见性、返回值和参数变化；
- import 变化；
- 继承和实现关系变化。

### 3.3 第三阶段：调用关系与影响范围

- 新增调用关系；
- 删除调用关系；
- 调用目标变化；
- 修改方法的直接调用者；
- 修改方法的上游调用者；
- 受影响的 Controller、定时任务和消息消费者；
- 在图谱中区分新增、删除、修改和受影响节点。

### 3.4 第四阶段：AI 变更分析

基于结构化 diff 和选中的代码 patch，生成：

- 变更概述；
- 功能变化；
- 技术变化；
- 影响范围；
- 潜在缺陷；
- 兼容性风险；
- 测试建议；
- 发布注意事项。

## 4. 总体架构

```text
┌─────────────────────────────────────────────┐
│ React 前端                                   │
│ 提交选择 / 文件变化 / Diff / 结构变化 / AI 结果 │
└──────────────────────┬──────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────┐
│ FastAPI API                                  │
│ commits / diff / comparison task / result   │
└──────────────┬───────────────┬──────────────┘
               │               │
┌──────────────▼──────┐ ┌──────▼────────────────┐
│ GitDiffService       │ │ ComparisonService     │
│ commit/ref 校验      │ │ 异步任务编排          │
│ 文件 diff/hunk       │ │ AST / graph 对比      │
└──────────────┬──────┘ └──────┬────────────────┘
               │               │
               ▼               ▼
          Git 仓库        Tree-sitter / Indexer
                               │
                               ▼
                         结构化对比结果
                               │
                               ▼
                         AI Insight 服务
```

### 4.1 与现有分析流程的关系

现有单版本分析流程保持不变：

```text
AnalysisService
  → GitManager.clone/pull
  → SymbolTableBuilder
  → CallGraphBuilder
  → FieldAccessBuilder
  → DependencyBuilder
```

新增提交对比流程独立实现：

```text
ComparisonService
  → GitDiffService
  → old/head 内容获取
  → 变化文件解析
  → 符号、调用图和依赖对比
  → 保存 comparison 结果
```

不能直接调用当前的全量 `AnalysisService.run_analysis()`，因为该流程会删除项目已有的分析数据。

## 5. 详细模块设计

## 5.1 Git 对比服务

建议新增：

```text
backend/app/services/analyzer/git_diff_service.py
```

职责：

- 获取仓库实例；
- 校验并解析 Git ref；
- 查询 commit 元数据；
- 计算文件级 diff；
- 读取 old/head 文件内容；
- 解析 patch 和 hunk；
- 限制文件和补丁大小；
- 标记二进制文件、截断内容和不支持的文件。

建议接口：

```python
class GitDiffService:
    async def list_commits(
        self,
        project_name: str,
        limit: int = 50,
        ref: str | None = None,
    ) -> list[CommitInfo]: ...

    async def resolve_commit(
        self,
        project_name: str,
        ref: str,
    ) -> CommitInfo: ...

    async def compare_commits(
        self,
        project_name: str,
        base_ref: str,
        head_ref: str,
        file_pattern: str | None = None,
    ) -> CommitDiffResult: ...

    async def get_file_diff(
        self,
        project_name: str,
        base_ref: str,
        head_ref: str,
        path: str,
    ) -> FileDiffResult: ...
```

Git 操作优先使用 GitPython API。若必须使用底层 Git 命令，应使用参数列表方式调用，不能将用户输入拼接成 Shell 字符串。

## 5.2 GitManager 扩展

修改：

```text
backend/app/services/analyzer/git_manager.py
```

增加或抽取以下能力：

```python
get_repository(project_name)
list_commits(project_name, limit, ref)
resolve_commit(project_name, ref)
get_commit_info(project_name, commit_sha)
get_commit_file_content(project_name, commit_sha, path)
```

现有 `read_file()` 的路径安全检查可以复用，但 Git 历史文件读取还必须校验：

- 路径必须属于 commit tree；
- 路径不能是 `.git` 内部路径；
- 路径不能包含 `..` 穿越；
- 只允许读取仓库内相对路径。

## 5.3 对比任务编排服务

建议新增：

```text
backend/app/services/comparison_service.py
```

职责：

- 创建和管理对比任务；
- 控制并发数量；
- 更新进度和状态；
- 重试失败任务；
- 解析变化文件；
- 保存结构化结果；
- 确保临时资源清理。

建议流程：

```python
async def run_comparison(comparison_id):
    1. 加载对比任务
    2. 校验 base/head commit
    3. 获取 Git diff
    4. 筛选需要分析的文件
    5. 读取 old/head 文件内容
    6. 对变化 Java 文件做 AST 解析
    7. 比较类、方法、字段和依赖
    8. 比较调用关系
    9. 计算影响范围
    10. 保存结果
    11. 更新任务状态为 ready
```

异常时：

- 设置任务为 `error`；
- 保存错误信息；
- 保留原始 Git diff（如果已经成功获取）；
- 清理临时目录或 worktree；
- 不修改当前项目的全局 File/Symbol/Graph 数据。

## 5.4 AST 对比策略

### MVP 策略

只解析 diff 中发生变化的 Java 文件：

```text
base 文件内容 ──┐
                ├─ AST 解析 → old symbols
head 文件内容 ──┘
                         ↓
                    稳定键匹配
                         ↓
                    symbol changes
```

### 完整策略

后续引入独立版本快照：

```text
ProjectSnapshot(base)
ProjectSnapshot(head)
        ↓
分别建立索引和调用图
        ↓
比较两个 snapshot
```

两个 commit 的符号不能根据数据库 UUID 直接比较，因为不同版本重新解析后 UUID 可能不同。应使用稳定键：

```text
(file_path, qualified_name, kind, normalized_signature)
```

建议符号变化类型：

```text
added
 deleted
 modified
 renamed
 unchanged
```

方法变化可以附加：

```text
signature_changed
body_changed
visibility_changed
return_type_changed
parameters_changed
```

## 5.5 调用图和依赖对比

调用边使用稳定的调用者和被调用者标识：

```text
caller stable key → callee stable key
```

比较两个版本的边集合：

```text
added_edges = head_edges - base_edges
deleted_edges = base_edges - head_edges
```

依赖对比复用已有 `DependencyBuilder` 的解析结果，比较：

- import 新增；
- import 删除；
- 包依赖新增；
- 包依赖删除；
- 继承关系变化；
- 实现关系变化。

## 6. 数据模型设计

### 6.1 第一阶段建议

第一阶段可以不新增数据库表，直接实时计算 Git diff。这样能快速验证功能，也不会影响已有数据模型。

如果需要保存对比记录，可以先新增一个轻量的 `ComparisonTask` 表。

### 6.2 后续快照模型

完整结构化分析建议新增：

```text
backend/app/models/project_snapshot.py
backend/app/models/comparison.py
backend/app/models/comparison_file.py
```

#### ProjectSnapshot

```text
id
project_id
commit_sha
branch
commit_message
author
committed_at
status
parser_version
created_at
updated_at
```

唯一性建议：

```text
(project_id, commit_sha, parser_version)
```

#### ComparisonTask

```text
id
project_id
base_snapshot_id
head_snapshot_id
base_commit
head_commit
status
progress
options
summary
error_message
created_at
updated_at
```

#### ComparisonFile

```text
id
comparison_id
old_path
new_path
change_type
old_blob_sha
new_blob_sha
additions
deletions
patch
is_binary
is_truncated
old_snapshot_file_id
head_snapshot_file_id
```

原始 Git diff 和结构化分析结果建议分离保存，避免 AI 结果覆盖事实数据。

## 7. API 设计

建议新增：

```text
backend/app/api/comparisons.py
backend/app/schemas/comparison.py
```

并在 `backend/app/main.py` 中注册路由。

## 7.1 获取 commit 列表

```http
GET /api/v1/projects/{project_id}/commits?limit=50&ref=main
```

响应：

```json
[
  {
    "sha": "a1b2c3d4...",
    "short_sha": "a1b2c3d",
    "message": "新增订单风险校验",
    "author": "developer",
    "authored_at": "2026-09-06T10:00:00Z"
  }
]
```

## 7.2 获取两个提交的文件 diff

```http
GET /api/v1/projects/{project_id}/commit-diffs?base_commit=abc123&head_commit=def456
```

响应：

```json
{
  "base_commit": {
    "sha": "abc123",
    "message": "旧版本"
  },
  "head_commit": {
    "sha": "def456",
    "message": "新增风险校验"
  },
  "summary": {
    "files_changed": 8,
    "added_files": 2,
    "deleted_files": 1,
    "modified_files": 5,
    "renamed_files": 0,
    "additions": 120,
    "deletions": 35
  },
  "files": [
    {
      "old_path": "src/OrderService.java",
      "new_path": "src/OrderService.java",
      "change_type": "modified",
      "additions": 30,
      "deletions": 8,
      "is_binary": false,
      "is_truncated": false
    }
  ]
}
```

纯 diff 接口不要求项目状态为 `ready`。

## 7.3 获取单文件 diff

```http
GET /api/v1/projects/{project_id}/commit-diffs/file?base_commit=abc123&head_commit=def456&path=src/OrderService.java
```

响应：

```json
{
  "old_path": "src/OrderService.java",
  "new_path": "src/OrderService.java",
  "change_type": "modified",
  "old_content": "...",
  "new_content": "...",
  "patch": "@@ -10,6 +10,20 @@",
  "hunks": [
    {
      "old_start": 10,
      "old_count": 6,
      "new_start": 10,
      "new_count": 20,
      "lines": []
    }
  ],
  "is_binary": false,
  "is_truncated": false
}
```

## 7.4 创建结构化对比任务

```http
POST /api/v1/projects/{project_id}/comparisons
```

请求：

```json
{
  "base_commit": "abc123",
  "head_commit": "def456",
  "file_paths": [
    "src/OrderService.java",
    "src/OrderController.java"
  ],
  "analysis_level": "structure",
  "include_tests": false
}
```

响应：

```json
{
  "id": "comparison-id",
  "status": "pending",
  "progress": 0
}
```

## 7.5 查询任务状态

```http
GET /api/v1/comparisons/{comparison_id}
```

响应：

```json
{
  "id": "comparison-id",
  "status": "ready",
  "progress": 100,
  "summary": {
    "added_symbols": 12,
    "deleted_symbols": 4,
    "modified_symbols": 9,
    "added_call_edges": 3,
    "deleted_call_edges": 1
  }
}
```

## 7.6 查询结构化结果

```http
GET /api/v1/comparisons/{comparison_id}/result
```

响应内容包括：

```json
{
  "files": [],
  "symbol_changes": [],
  "dependency_changes": [],
  "call_graph_changes": [],
  "impact_scope": [],
  "risks": []
}
```

## 7.7 AI 分析接口

```http
POST /api/v1/comparisons/{comparison_id}/analyze
```

建议使用 SSE 返回流式结果，复用当前聊天功能的流式处理模式，但不混用普通项目聊天会话。

AI 输入应为结构化上下文：

```json
{
  "commits": {},
  "summary": {},
  "changed_files": [],
  "changed_symbols": [],
  "call_graph_changes": [],
  "dependency_changes": [],
  "selected_patches": []
}
```

AI 输出建议：

```json
{
  "overview": "本次提交主要增加订单风险校验能力",
  "feature_changes": [],
  "technical_changes": [],
  "impact_scope": [],
  "potential_risks": [],
  "breaking_changes": [],
  "test_recommendations": []
}
```

## 8. 前端设计

## 8.1 新增页面

```text
frontend/src/pages/ComparisonPage.tsx
frontend/src/pages/ComparisonPage.css
```

建议路由：

```text
/projects/:projectId/compare
```

## 8.2 新增组件

```text
frontend/src/components/Comparison/
├── CommitSelector.tsx
├── ComparisonSummary.tsx
├── ChangedFileList.tsx
├── DiffViewer.tsx
├── SymbolChangeList.tsx
├── CallGraphChangeList.tsx
└── RiskSummary.tsx
```

## 8.3 页面布局

```text
┌─────────────────────────────────────────────┐
│ 项目名称                                      │
│ Base [commit]  →  Head [commit]              │
│ [查看 Diff] [开始结构分析] [AI 分析]           │
├────────────────┬────────────────────────────┤
│ 变化文件列表    │ 文件 Diff / 分析结果          │
│                │                            │
│ M Order.java   │ 旧版本       新版本           │
│ A Risk.java    │ 删除行       新增行           │
│ D Test.java    │                            │
└────────────────┴────────────────────────────┘
```

## 8.4 前端 API 和状态

修改：

```text
frontend/src/services/api.ts
frontend/src/types/index.ts
frontend/src/App.tsx
```

新增：

```text
frontend/src/store/comparisonStore.ts
```

建议类型：

```typescript
export interface GitCommit {
  sha: string;
  short_sha: string;
  message: string;
  author: string;
  authored_at: string;
}

export type ChangeType =
  | 'added'
  | 'deleted'
  | 'modified'
  | 'renamed'
  | 'copied';

export interface ChangedFile {
  old_path: string | null;
  new_path: string | null;
  change_type: ChangeType;
  additions: number;
  deletions: number;
  is_binary: boolean;
  is_truncated: boolean;
}
```

`comparisonStore` 管理：

- commit 列表；
- base/head 选择；
- diff 文件列表；
- 当前选中文件；
- 单文件 patch；
- 结构化任务状态；
- AI 分析结果；
- 加载和错误状态。

## 9. 文件改动清单

### 9.1 第一阶段预计改动

```text
backend/app/services/analyzer/git_manager.py       修改
backend/app/services/analyzer/git_diff_service.py  新增
backend/app/api/comparisons.py                     新增
backend/app/schemas/comparison.py                  新增
backend/app/main.py                                修改

frontend/src/App.tsx                               修改
frontend/src/services/api.ts                       修改
frontend/src/types/index.ts                        修改
frontend/src/pages/ComparisonPage.tsx              新增
frontend/src/pages/ComparisonPage.css               新增
frontend/src/store/comparisonStore.ts              新增
frontend/src/components/Comparison/*                新增
```

### 9.2 第二阶段预计改动

```text
backend/app/services/comparison_service.py         新增
backend/app/services/comparison/symbol_diff.py     新增
backend/app/services/comparison/dependency_diff.py 新增
backend/app/models/project_snapshot.py             新增
backend/app/models/comparison.py                   新增
backend/app/models/comparison_file.py              新增
backend/app/db/init_db.py                          修改
```

### 9.3 第三阶段预计改动

```text
backend/app/services/comparison/graph_diff.py      新增
backend/app/services/chain_traversal.py            修改或扩展
backend/app/services/graph_service.py              修改或扩展
frontend/src/components/Comparison/CallGraphChangeList.tsx 修改
frontend/src/components/Graph/*                    适配变更状态颜色
```

### 9.4 第四阶段预计改动

```text
backend/app/services/agent/prompt_manager.py       增加对比 Prompt
backend/app/services/agent/langgraph_client.py     增加对比上下文
backend/app/api/comparisons.py                     增加 SSE AI 接口
frontend/src/components/Comparison/RiskSummary.tsx 增强
```

## 10. 安全与边界处理

### 10.1 commit/ref 校验

必须处理：

- ref 不存在；
- 两个 ref 相同；
- 非 commit 对象；
- 非法或过长输入；
- merge commit 的比较方向；
- shallow clone 中对象不存在。

建议通过 GitPython 的 commit 解析能力验证 ref，而不是手动执行未经校验的 Shell 命令。

### 10.2 路径安全

- 只允许仓库内相对路径；
- 拒绝 `../` 路径；
- 拒绝绝对路径；
- 不允许访问 `.git` 目录；
- 对 old_path 和 new_path 都做校验；
- 不纳入未追踪工作区文件。

### 10.3 资源限制

建议默认限制：

```text
commit 列表最多 100 条
单次变化文件最多 500 个
单文件内容最多 1 MB
单个 patch 最多 5 MB
单次结构分析最多 200 个 Java 文件
```

超出限制时：

- 返回可识别的 `is_truncated`；
- 不让整个任务失败；
- 在页面上提示用户缩小文件范围。

### 10.4 文件类型

第一阶段默认重点支持 Java 源文件，并沿用当前测试文件排除规则。同时建议将文件筛选规则配置化，以便后续支持：

- JavaScript/TypeScript；
- Python；
- Kotlin；
- 配置文件；
- 测试文件开关。

二进制文件不进行文本 patch 展示，只显示文件状态和大小变化。

## 11. 测试设计

当前项目实际测试覆盖较少，因此该功能应同步补充测试。

### 11.1 Git 服务单元测试

- 合法 SHA 能够解析；
- 分支名和 tag 能够解析；
- 非法 ref 返回明确错误；
- 两个相同 commit 返回空 diff；
- 修改文件识别正确；
- 新增文件识别正确；
- 删除文件识别正确；
- 重命名文件识别正确；
- 二进制文件正确标记；
- 大文件和大 patch 正确截断；
- 测试目录筛选正确；
- Java 文件筛选正确；
- 路径穿越被拒绝。

### 11.2 API 测试

- 项目不存在；
- 仓库不存在；
- commit 不存在；
- 文件路径不属于仓库；
- 返回结构符合 Pydantic schema；
- diff 不要求项目处于 READY；
- 对比任务状态能够正确更新。

### 11.3 AST 对比测试

- 新增类；
- 删除类；
- 新增方法；
- 删除方法；
- 方法体修改；
- 方法签名修改；
- 方法重载不会错误合并；
- 文件重命名后的符号匹配；
- 两个版本的符号 UUID 不同时仍能正确匹配。

### 11.4 任务和资源测试

- 任务失败后状态为 error；
- 任务重试次数符合配置；
- 并发任务数量受限制；
- 任务失败后临时目录能够清理；
- 对比任务不会删除当前项目 File/Symbol/Graph 数据。

## 12. 实施顺序

### 第一步：确认数据库策略

确认当前环境是使用 `create_all` 还是 Alembic。第一期如果不持久化对比结果，可以暂时不引入迁移。

### 第二步：实现 Git Diff MVP

完成：

```text
commit 列表
+ 文件级 diff
+ 增删行统计
+ 单文件 patch
+ 边界和安全校验
```

### 第三步：完成前端闭环

完成：

```text
项目入口
+ commit 选择
+ 文件列表
+ Diff Viewer
+ 筛选和统计
```

### 第四步：加入结构化对比任务

对变化 Java 文件进行 old/head AST 解析，输出类、方法和依赖变化。

### 第五步：加入调用图影响分析

比较调用边，并基于现有调用链能力计算上下游影响范围。

### 第六步：接入 AI 分析

基于结构化上下文输出变更总结、风险和测试建议。

## 13. 推荐的 MVP 验收标准

第一阶段完成后，用户可以：

1. 进入一个已有项目；
2. 查看该仓库的最近 commit；
3. 选择两个不同 commit；
4. 查看文件新增、删除、修改和重命名状态；
5. 查看新增行和删除行统计；
6. 点击文件查看 old/head 内容和 patch；
7. 对 Java 文件和测试文件进行筛选；
8. 对非法 commit、空 diff、二进制文件和超大 patch 看到明确提示；
9. 使用该功能不会影响当前项目已有的符号、调用图和代码问答功能。

## 14. 最终建议

建议采用渐进式实现，不要第一步就改造当前的全量分析模型。

最稳妥的落地路线是：

```text
独立 Git Diff 服务
    ↓
前端提交对比页面
    ↓
变化 Java 文件 AST 对比
    ↓
调用图和依赖影响分析
    ↓
AI Code Review
```

这样可以先用较小改动验证产品价值，再根据实际使用情况引入 `ProjectSnapshot` 和完整历史版本索引，避免破坏现有单版本分析流程。
