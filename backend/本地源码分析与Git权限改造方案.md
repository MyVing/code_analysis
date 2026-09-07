# 本地源码分析与 Git 权限改造方案

## 1. 背景与目标

当前项目由后端直接克隆 Git 仓库，并将源码保存到服务端 `WORKSPACE_DIR` 中，再基于服务端工作区完成源码解析、索引构建、Git 对比和 Agent 源码问答。

这种方式不适合面向普通用户使用，主要问题包括：

- 后端需要访问用户的 Git 仓库；
- 用户源码会持久化保存到服务器本地；
- 可能需要处理私有仓库凭证；
- 后端可以读取整个项目，而不只是用户授权的内容；
- 用户本地未提交的代码无法直接参与分析；
- 多用户场景下需要额外处理工作区隔离、清理和路径安全。

目标架构是：

> 用户在本地持有项目源码，由本地分析客户端负责扫描源码、检测 Git 状态和构建索引；后端只保存项目元数据、结构化索引、分析结果和源码快照指纹。涉及源码细节时，按需请求本地客户端返回最小范围的代码片段，不在服务器持久化完整源码。

---

## 2. 当前实现情况

当前主要流程如下：

```text
用户提交 git_url 和 branch
        ↓
后端调用 GitManager.clone()
        ↓
克隆到 WORKSPACE_DIR/{project_name}
        ↓
读取源码并构建符号表、调用图、依赖图
        ↓
Agent 和 Git 对比功能继续读取后端工作区
```

关键代码位置：

- `app/services/analyzer/git_manager.py`
- `app/services/analysis_service.py`
- `app/services/indexer/symbol_builder.py`
- `app/tools/code_tools.py`
- `app/api/files.py`
- `app/services/analyzer/git_diff_service.py`
- `app/core/config.py`

当前后端执行的关键操作包括：

```python
git.Repo.clone_from(...)
repo.remotes.origin.pull(...)
```

以及通过项目名称拼接服务端工作区路径：

```text
WORKSPACE_DIR/{project_name}
```

---

## 3. 推荐总体架构

```text
用户本地项目目录
        │
        ▼
本地分析客户端
        │
        ├── 检测 Git 状态
        ├── 扫描源码文件
        ├── 计算源码快照指纹
        ├── 构建本地分析索引
        ├── 上传结构化索引
        ├── 上传索引变更信息
        └── 按需返回源码片段
        │
        ▼
后端平台
        │
        ├── 保存项目元数据
        ├── 保存源码快照标识
        ├── 保存符号表和关系图
        ├── 保存分析报告
        ├── 判断索引是否过期
        └── 发起源码片段请求
```

后端不再负责：

- 克隆 Git 仓库；
- 拉取远程分支；
- 保存完整源码；
- 保存 `.git` 目录；
- 保存用户 Git 凭证；
- 直接读取用户本地绝对路径。

---

## 4. 本地客户端形态

### 4.1 第一阶段推荐：CLI 客户端

建议首先提供 CLI：

```bash
code-analysis connect --project-id <project-id> --path D:\projects\demo
code-analysis index
code-analysis status
code-analysis ask "分析订单创建流程"
```

本地 CLI 负责：

- 接收用户选择的本地项目目录；
- 扫描 Git 状态；
- 过滤参与分析的文件；
- 计算源码快照指纹；
- 构建符号表、调用图、依赖图；
- 将结构化索引上传到后端；
- 根据后端请求返回指定源码片段。

优点：

- 开发成本较低；
- 权限边界清晰；
- 源码只由用户本地程序读取；
- 适合开发人员、CI 和自动化场景。

### 4.2 第二阶段：桌面客户端

后续可以使用 Electron、Tauri 等封装桌面程序，提供：

- 本地目录选择；
- 索引进度展示；
- 文件变化监听；
- “索引已过期”提示；
- Git 对比结果展示；
- 本地源码请求确认。

### 4.3 不建议的方式：纯浏览器访问本地目录

浏览器对本地目录的访问权限、生命周期和后台任务能力有限，不建议作为正式核心架构。可以作为桌面客户端的辅助界面。

---

## 5. 源码快照标识符设计

不能只依赖 Git commit，因为用户可能存在：

- 未提交修改；
- 已暂存但未提交的修改；
- 未跟踪文件；
- 分支切换；
- 删除文件；
- 本地新增但尚未推送的代码。

### 5.1 `source_snapshot_id`

建议根据实际参与分析的源码内容生成源码快照标识符：

```text
source_snapshot_id = SHA-256(
    分支名或 HEAD commit
    + 文件相对路径
    + 文件内容 hash
    + 文件大小
    + 文件状态
)
```

示例：

```json
{
  "branch": "feature/order",
  "head_commit": "a1b2c3d",
  "working_tree_dirty": true,
  "tracked_files": 120,
  "untracked_files": 3,
  "content_digest": "sha256:...",
  "snapshot_id": "sha256:..."
}
```

建议只将参与分析的文件纳入摘要，例如 Java 源文件和必要的配置文件，避免 README、图片等无关文件变化导致重建。

### 5.2 `analysis_fingerprint`

源码不变时，分析器升级也可能要求重建，因此需要加入分析器版本信息：

```text
analysis_fingerprint = SHA-256(
    source_snapshot_id
    + analyzer_version
    + parser_version
    + index_schema_version
    + analysis_config
)
```

后端保存当前分析结果的 `analysis_fingerprint`，客户端重新计算后进行比较：

```text
客户端 fingerprint == 后端 fingerprint
    → 当前索引有效

客户端 fingerprint != 后端 fingerprint
    → 需要重建索引
```

### 5.3 不建议只监听 `.git/index`

`.git/index` 只能反映 Git 暂存区的变化，不能完整反映工作区源码变化。因此应该基于实际源码内容计算指纹，而不是只判断 `.git/index` 是否变化。

---

## 6. 后端数据保存策略

### 6.1 可以保存的数据

- 项目 ID；
- 项目名称；
- 用户 ID；
- 分支名；
- HEAD commit；
- `source_snapshot_id`；
- `analysis_fingerprint`；
- 分析器版本；
- 文件相对路径；
- 文件 hash、大小和语言；
- 符号表；
- 类、方法、字段信息；
- 调用关系；
- 依赖关系；
- 字段访问关系；
- 分析报告；
- Git diff 的结构化结果；
- 用户主动允许上传的源码片段。

### 6.2 默认不保存的数据

- 完整 Git 仓库；
- `.git` 目录；
- Git 用户名、密码、Token 或 SSH 私钥；
- 完整源码文件；
- 用户本地绝对路径；
- 与分析无关的二进制文件；
- `.env`、密钥和凭证文件。

当前 `File` 表可以继续保存文件元数据，但不应将完整源码正文作为长期持久化字段。

---

## 7. 索引构建与重建策略

### 7.1 第一版：本地全量重建

第一版建议优先实现稳定的全量流程：

1. 本地扫描源码；
2. 计算 `source_snapshot_id`；
3. 对比服务器保存的指纹；
4. 指纹相同时跳过分析；
5. 指纹不同时本地全量构建索引；
6. 上传新的结构化索引和指纹。

### 7.2 后续：增量索引

本地客户端计算文件变化集合：

```json
{
  "added": ["src/NewService.java"],
  "modified": ["src/OrderService.java"],
  "deleted": ["src/OldService.java"]
}
```

后端或本地索引器再执行：

- 新增文件的索引；
- 修改文件的重新解析；
- 删除文件的索引清理；
- 受影响调用边的重建；
- 受影响依赖关系的更新。

---

## 8. Agent 源码问答改造

当前 Agent 工具依赖后端工作区读取文件，例如：

```text
backend workspace → read_file()
```

建议改为两类问题分别处理。

### 8.1 结构化索引问题

以下问题只需要后端索引，不需要源码正文：

- 某个方法被谁调用；
- 某个类有哪些实现类；
- 两个模块之间有什么依赖；
- 某字段在哪些地方被访问；
- 某接口有哪些实现。

这类请求直接查询后端保存的符号表和图数据。

### 8.2 源码细节问题

以下问题需要具体源码：

- 某方法内部的异常处理逻辑；
- 订单创建流程具体如何实现；
- 某段代码为什么存在问题；
- 某个分支条件实际做了什么。

处理方式：

1. 后端根据索引定位相关文件、符号和行范围；
2. 向本地客户端请求最小必要代码片段；
3. 本地客户端读取对应范围；
4. 只返回必要源码内容；
5. 后端或模型完成临时分析；
6. 默认不将源码片段写入长期数据库。

这样可以做到：

> 后端不保存完整源码，源码细节只在必要时、以最小范围临时传输。

---

## 9. 建议的后端接口

### 9.1 创建项目

```http
POST /projects
```

创建逻辑项目。`git_url` 可以改成可选展示信息，也可以完全取消。

### 9.2 上传本地快照信息

```http
POST /projects/{project_id}/snapshot
```

示例：

```json
{
  "branch": "feature/order",
  "head_commit": "a1b2c3d",
  "snapshot_id": "sha256:...",
  "analysis_fingerprint": "sha256:...",
  "files": [
    {
      "path": "src/OrderService.java",
      "sha256": "...",
      "size": 3456,
      "language": "java"
    }
  ]
}
```

### 9.3 上传结构化索引

```http
POST /projects/{project_id}/index
```

上传内容包括：

- 文件元数据；
- 类和方法；
- 符号表；
- 调用关系；
- 依赖关系；
- 字段访问关系；
- 分析器版本；
- 当前快照指纹。

### 9.4 检查索引状态

```http
GET /projects/{project_id}/index-status
```

返回示例：

```json
{
  "indexed": true,
  "up_to_date": false,
  "requires_reindex": true,
  "reason": "source_snapshot_changed",
  "server_snapshot_id": "sha256:..."
}
```

### 9.5 请求源码片段

```http
POST /projects/{project_id}/source-request
```

示例：

```json
{
  "path": "src/OrderService.java",
  "symbol": "OrderService.createOrder",
  "start_line": 40,
  "end_line": 90,
  "max_bytes": 20000
}
```

本地客户端返回：

```json
{
  "path": "src/OrderService.java",
  "start_line": 40,
  "end_line": 90,
  "content": "...",
  "snapshot_id": "sha256:..."
}
```

---

## 10. Git 对比功能改造

Git 对比也不应再依赖服务器上的完整仓库，应由本地客户端执行：

```text
本地 Git 仓库
    ↓
计算 base/head commit
    ↓
获取 changed files 和 diff
    ↓
上传结构化变更结果或必要 diff
    ↓
后端生成对比报告
```

示例：

```json
{
  "base_commit": "1111111",
  "head_commit": "2222222",
  "changed_files": [
    {
      "path": "src/OrderService.java",
      "status": "modified",
      "additions": 20,
      "deletions": 5
    }
  ],
  "summary": {
    "files": 1,
    "additions": 20,
    "deletions": 5
  }
}
```

如果需要 AI 分析 diff，只上传：

- 必要的 diff 文本；
- 相关文件片段；
- 结构化变更信息。

不需要上传整个 Git 仓库。

---

## 11. 安全边界

### 11.1 客户端上传内容校验

后端必须校验：

- 用户身份；
- 项目归属；
- 请求签名或访问令牌；
- 文件路径格式；
- 单次请求大小；
- 索引数据格式；
- `snapshot_id` 的一致性。

### 11.2 项目数据隔离

所有查询必须同时校验：

```text
user_id + project_id
```

不能只依赖 UUID 防止越权访问。

### 11.3 源码请求限制

源码请求必须限制：

- 只能请求相对路径；
- 禁止 `.git` 路径；
- 禁止 `..` 路径穿越；
- 限制最大行数；
- 限制最大字节数；
- 只能请求索引中存在的文件或符号；
- 必要时要求用户在本地确认。

### 11.4 敏感文件过滤

默认禁止上传：

```text
.env
*.pem
*.key
id_rsa
credentials*
application-secret*
```

同时禁止客户端将以下目录加入索引：

```text
.git
node_modules
 target
 build
 dist
```

具体目录应根据语言和项目类型配置。

### 11.5 日志脱敏

后端日志中不得记录：

- 源码正文；
- Git Token；
- SSH 私钥；
- 用户本地完整路径；
- 未脱敏的源码请求内容。

---

## 12. 推荐迁移顺序

### 阶段一：抽象分析输入

保留当前分析器逻辑，但把输入从固定服务端工作区改成抽象的源码输入：

```python
AnalysisInput(
    project_id=project_id,
    source_root=local_or_temp_root,
    snapshot_id=snapshot_id,
)
```

同时开发本地 CLI，先支持从本地目录启动分析。

### 阶段二：将解析和索引迁移到本地

迁移以下能力：

- 文件扫描；
- Tree-sitter 解析；
- 符号表构建；
- 调用关系提取；
- 依赖关系提取；
- 字段访问关系提取。

后端改为只接收结构化索引。

### 阶段三：改造 Agent 工具

逐步改造：

- `app/tools/code_tools.py`；
- `app/api/files.py`；
- `app/services/agent/langgraph_client.py`；
- 源码读取工具；
- Prompt 中的源码访问逻辑。

结构化问题查询后端索引，源码问题通过本地客户端按需提供片段。

### 阶段四：迁移 Git 对比

将 `git_diff_service.py` 中依赖服务端仓库的逻辑移到本地客户端，只向后端上传结构化 diff 或必要的 patch。

### 阶段五：移除后端工作区

确认所有功能不再依赖服务器源码后：

- 删除 `WORKSPACE_DIR`；
- 删除 `GitManager.clone()` 和 pull 逻辑；
- 删除后端项目目录清理逻辑；
- 删除 Git 凭证相关配置；
- 增加源码不落盘测试；
- 增加越权、路径穿越和敏感文件过滤测试。

---

## 13. 三种源码保护级别

### 方案 A：源码不持久化，但允许临时传输代码片段

特点：

- 完整源码只在用户本地；
- 模型分析时允许上传必要片段；
- 后端不长期保存源码；
- 最适合当前 Agent 架构。

这是推荐的第一阶段方案。

### 方案 B：源码完全不离开用户机器

特点：

- 源码、索引和模型调用全部在用户本地；
- 需要本地模型或本地推理服务；
- 后端只接收分析结果。

安全性最高，但架构和部署成本最大。

### 方案 C：源码只进入服务端内存，不写入磁盘

特点：

- 允许源码临时上传；
- 服务端只在内存中处理；
- 需要严格控制日志、异常、缓存和中间件；
- 仍然需要考虑服务商和运行环境是否可能读取内存。

---

## 14. 最终建议

建议采用以下落地路线：

```text
第一版：本地 CLI + 指纹检查 + 本地全量索引 + 后端保存结构化结果
第二版：本地源码片段按需请求 + Agent 混合查询
第三版：本地增量索引 + 本地 Git diff
第四版：桌面客户端
第五版：支持源码完全不离开本地的本地模型模式
```

推荐的第一版原则：

1. 后端不再 clone 或 pull 用户仓库；
2. 用户源码只由本地客户端读取；
3. 后端保存 `source_snapshot_id` 和 `analysis_fingerprint`；
4. 只上传符号、关系图和文件元数据；
5. 源码细节按需返回最小范围代码片段；
6. 服务端不持久化完整源码；
7. Git 对比由本地客户端执行；
8. 后续再增加增量索引和桌面端能力。

该方案既能保留现有后端分析结果和图查询能力，又能避免后端持有用户完整项目源码，适合作为当前项目的渐进式改造方向。
