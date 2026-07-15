# API 版本化策略

## 当前状态

MVP 阶段使用 `/api` 前缀，不区分版本号。所有端点直接挂在 `/api` 下。

## 端点清单

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/projects/` | GET | 项目列表 |
| `/api/projects/` | POST | 创建项目 |
| `/api/projects/{id}` | GET | 项目详情 |
| `/api/projects/{id}` | DELETE | 删除项目 |
| `/api/projects/{id}/analyze` | POST | 触发分析 |
| `/api/projects/{id}/files` | GET | 项目文件列表 |
| `/api/projects/{id}/status` | PATCH | 更新项目状态 |
| `/api/symbols/` | GET | 查询符号 |
| `/api/symbols/{id}` | GET | 符号详情 |
| `/api/symbols/file/{id}` | GET | 文件符号列表 |
| `/api/symbols/{id}/children` | GET | 子符号列表 |
| `/api/graph/call-graph/{id}` | GET | 调用图 |
| `/api/graph/imports/{id}` | GET | 导入关系 |
| `/api/graph/visualization/{id}` | GET | 图可视化 |
| `/api/graph/call-graph/{id}/expand/{sid}` | GET | 展开符号图 |
| `/api/graph/file-symbols/{id}/{fid}` | GET | 文件符号图 |
| `/api/graph/expand-call/{id}/{sid}` | GET | 展开调用 |
| `/api/graph/expand-class-calls/{id}/{sid}` | GET | 展开类调用 |
| `/api/graph/full-chain/{id}/{sid}` | GET | 完整链路 |
| `/api/files/{id}/content` | GET | 文件内容 |
| `/api/chat/{id}` | POST | AI 对话 |

## 未来版本化方案

当 API 发生不兼容变更时，引入版本前缀：

1. 新建 `app/api/v2/` 目录，包含变更后的路由
2. 在 `app/api/__init__.py` 中同时注册 v1 和 v2 路由
3. 旧版本标记为 Deprecated，在响应头中添加 `Deprecation` 和 `Sunset` 字段
4. 旧版本至少保留 2 个版本周期后移除
5. 在此文档中记录迁移指南

### 版本生命周期

- **Active**: 当前推荐使用的版本
- **Deprecated**: 仍可用但不推荐，响应头包含弃用通知
- **Retired**: 已移除，请求返回 410 Gone
