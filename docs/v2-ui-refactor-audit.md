# Phase 0 — Baseline & UI Audit

## 1. Git 状态与环境事实

- **当前分支**: `refactor/ui-v2` (从 `v1.8.1` / `206bf0dab358917940722e1e846d8b80de3f8221` 签出)
- **Base Tag**: `v1.8.1`
- **Base Commit**: `206bf0dab358917940722e1e846d8b80de3f8221`
- **Initial HEAD**: `206bf0dab358917940722e1e846d8b80de3f8221`
- **工作区状态**: Clean

## 2. 真实执行的门禁结果 (Baseline Test Matrix)

| 检查项 | 命令 | 结果 | 详情 |
|---|---|---|---|
| Frontend Vitest | `cd frontend && npm run test` | **PASS** | 43 test files, 303 passed |
| Frontend Typecheck & Build | `cd frontend && npm run build` | **PASS** | `vue-tsc --noEmit && vite build` 成功通过 |
| OpenAPI 契约一致性 | `cd frontend && npm run check:api-types` | **PASS** | openapi-typescript 7.13.0 一致 |
| Frontend Bundle Check | `cd frontend && npm run check:bundle` | **PASS** | Largest chunk 272.8 KiB (index) |
| Backend Pytest Suite | `cd backend && PYTHONPATH=. .venv/bin/pytest -q` | **PASS** | 324 passed, 38 skipped |
| Frontend Lint | `npm run lint` | **NOT AVAILABLE** | package.json 中未定义 lint 脚本 |
| Browser Smoke | `playwright test` | **NOT VERIFIED** | 本地未启动全套 backend/db/redis 服务 |
| E2E | `playwright test` | **NOT VERIFIED** | 本地未启动全套 backend/db/redis 服务 |

## 3. UI 架构与现有模式盘点

1. **Tokens 与样式**: `src/styles/global.css` 包含 `--if-*` 系列变量和 Element Plus 变量映射。
2. **App Shell**: `src/layouts/AppLayout.vue`，深色侧边栏 + 顶部移动端 Header + 桌面主工作区。
3. **共享 UI 组件**:
   - `PageHeader.vue`: 页面标题区、eyebrow、description、actions 插槽
   - `StatusTag.vue`: 业务状态徽章，支持 6 种语义色 (neutral, info, progress, warning, success, danger)
   - `SectionCard.vue`: 区块卡片
   - `ListCard.vue`: 移动端列表卡片
   - `ListFilterPanel.vue`: 筛选面板
   - `EmptyState.vue` / `ErrorState.vue`: 状态占位
   - `AppIcon.vue`: 统一内联 SVG 图标
   - `InfoGrid.vue`: 属性网格
4. **核心业务页面**:
   - `Feedback`: ListView, DetailView, CreateView
   - `Requirement`: ListView, DetailView, CreateView
   - `Version`: ListView, DetailView, CreateView
   - `Release`: ListView, DetailView
5. **管理与支持页面**:
   - `UserListView`, `RoleListView`, `SystemCatalogView`, `AuditCenterView`, `NotificationCenterView`, `ProfileView`, `LoginView`, `ChangePasswordView`, `ForbiddenView`

## 4. 详情抽屉加载修复（2026-10-08）

- 实际本地域名复现：从版本列表打开详情，组件读取列表路由中不存在的 `id`，请求 `/api/v1/versions/NaN` 并收到 422。
- 反馈、需求、版本详情组件声明并读取 `embedded` / `embeddedId`；抽屉使用列表传入的实体 ID，独立详情页仍使用路由 ID。列表按选中实体 ID 设置组件 key，隔离不同记录的详情及编辑状态。
- 修改文件：三类实体的 ListView / DetailView，以及 `frontend/e2e/detail-drawer.spec.ts`。无后端、契约、migration 或权限变更，无规格冲突。
- 新浏览器回归：桌面 1280px、移动 390px，三类抽屉打开两个不同记录、详情关联请求、展开完整页面及返回原筛选/分页列表，**6 passed**。修复前版本抽屉用例失败，修复后通过。
- 既有编辑提示与 revision 冲突浏览器回归：**11 passed**；Frontend Vitest **303 passed / 43 files**；Typecheck + Build、`git diff --check` 均 PASS。
- 实际 admin 登录验收：本地域名中 `1.0.0 / ceshi` 版本抽屉和完整详情页正常加载，版本详情及需求清单接口返回 200，无页面运行错误。已重新构建本地页面；本节不表示完整主链路或正式 CI 验收完成。

## 5. 合并评估发现的回归修复（2026-10-08）

- 评估发现：从带分页、筛选的反馈列表打开抽屉，沿需求 → 版本 → 发布记录返回时，原列表条件丢失；既有 V1.8 主链导航用例在 375 / 390 / 768 / 1280 / 1440px 五个视口均失败。嵌入详情现在通过 `listTarget` 从当前列表路由提取白名单查询字段；独立详情继续校验 `return_to`，不允许外部地址或嵌套跳转。
- 评估发现：在抽屉中修改成功，详情更新而列表仍显示旧标题。反馈、需求、版本详情现在在服务端写入成功后发出 `updated`，由父列表使用当前已应用条件重新加载。覆盖编辑、状态、反馈转需求、版本发布及需求关联操作；保存失败或 revision 409 不发送成功事件。
- 新浏览器用例覆盖三类实体、1280 / 390px：编辑标题后关闭抽屉看到新值，重新打开后用最新 revision 改状态，记录离开当前筛选结果且其他记录保留，有效分页和状态条件不变。修复前需求编辑用例失败（列表没有再次请求）；修复后新增编辑及既有抽屉用例共 **12 passed**。
- 新导航单元测试覆盖三类列表上下文、独立详情、路由变化、外部地址、嵌套和重复参数；既有组件测试补充普通失败 / 409 无成功事件、显式刷新 revision 后保存只发送一次成功事件的断言。
- 本地门禁：Frontend Vitest **310 passed / 44 files**；Typecheck + Build、API 类型一致性、Bundle（最大 JavaScript chunk 272.9 KiB）及 `git diff --check` PASS。最终本地浏览器回归 **154 passed**，覆盖全部模拟接口用例，包括管理、系统与模块、响应式页面、关联导航、编辑提示和并发冲突。
- 本地浏览器测试地址为 `http://127.0.0.1:5173`；两个会创建真实业务数据的 release smoke 用例留给 GitHub CI 的隔离 Compose 环境执行，不对现有本地账号和业务数据运行它们。完整六项 CI 结果应核对该分支最终提交对应的 GitHub Actions 记录；本节只记录已经完成的本地验证。
- 本节变更仅涉及前端详情、列表、导航及回归测试和本审计文档。无后端 / 契约 / migration / permission / 状态机变更，无规格冲突。同一 Agent 的复查不称为外部独立终审。master 与 v1.8.1 保持 `206bf0dab358917940722e1e846d8b80de3f8221`；尚未合并、发布或部署。
