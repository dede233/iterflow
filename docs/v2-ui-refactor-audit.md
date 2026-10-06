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
