# 协作流程优化实施记录

## 2026-10-31 开工与范围冻结

用户在方案交付后明确授权开工。开发分支为 `codex/collaboration-workflow`，复用当前工作目录；开始时仅有上一轮新增、尚未提交的方案文档，无其他未提交改动。

按方案推荐默认值实施：反馈接收人不自动扩大读取范围；需求取消总负责人，保留历史访问依据；多人设计／开发不强制会签；取消独立排期；邮件默认仅待办与上线；批量关联全成全败。正式版本号暂不变，实际环境迁移、合并发布和部署未执行。

AGENTS.md、DEVELOPMENT.md、TASKS.md 已区分本轮开发授权与历史发布授权。阶段 0 的产品范围和实施默认值已冻结。各新增能力仍须先更新开发契约及状态规格，再实施后端、迁移与前端；本批次复用已有读取和反馈写入契约，无新增 API 或状态变化。

## 阶段 1 表单精简与摘要体验

### 已实现

- 反馈新建／编辑移除期望结果与实际结果字段，并从写入 payload 移除；旧值在详情显示为历史补充信息，不清空数据库历史值。
- 版本需求清单的桌面“查看”和手机卡片“查看”改为摘要弹窗，包含需求描述、验收标准、状态、优先级、类型及权限范围内的来源反馈。
- 保留完整详情入口；关闭摘要不改变当前版本路由、清单状态和页面上下文。
- 摘要独立执行需求权限检查与 scoped GET；来源反馈读取失败不阻断摘要；关闭、切换需求或账号／权限改变时清空旧数据并拒绝过期异步响应。
- 手机摘要使用实际全屏尺寸，桌面和平板采用居中弹窗；弹窗挂载到 body，以支持版本详情已处于弹层的情况。

### 修改文件

- `frontend/src/views/feedback/FeedbackCreateView.vue`
- `frontend/src/views/feedback/FeedbackDetailView.vue`
- `frontend/src/views/version/VersionDetailView.vue`
- `frontend/src/components/RequirementSummaryDialog.vue`
- `frontend/src/components/RequirementSummaryDialog.spec.ts`
- `frontend/src/views/detailViews.component.spec.ts`
- `frontend/e2e/collaboration-summary.spec.ts`
- `frontend/components.d.ts`（组件自动生成声明）
- 当前授权／任务文档、方案与本记录。

### 实际验证结果

| 检查 | 结果与边界 |
| --- | --- |
| 前端全量 Vitest | 48 个测试文件，328 项通过；包含历史值不被编辑覆盖、摘要权限撤销、旧响应隔离、403／404／500 与重试 |
| vue-tsc 与 Vite build | 通过 |
| check:api-types | 通过，当前开发契约未改变 |
| check:bundle | 通过，最大 JS chunk 273.7 KiB |
| Playwright 摘要与表单测试 | 375、390、768、1280、1440 五个视口全部通过 |
| 截图复核 | 手机与平板实际截图复核；修正手机全屏被全局弹窗边距覆盖的问题 |
| git diff --check | 通过 |

浏览器使用单独的本地 Vite 端口 5178，并拦截 API 返回固定测试数据；这是实际浏览器 UI 验证，不是完整后端端到端验收，也未使用真实业务数据。未运行后端、PostgreSQL、Docker 或远端六项 CI，因为本批次没有后端／契约／数据库变更；这些门禁保留在后续对应阶段和最终验收。

首次浏览器测试中两个手机用例因断言了外层 overlay 而非 dialog 面板的 fullscreen class 失败，修正定位后五项通过。随后截图发现手机尺寸受全局 CSS 限制，修正本组件样式并增加实际宽高断言，再跑五视口全部通过。测试截图禁用动画以避免捕获淡入过程；固定测试数据的 completion_rate 修正为契约中的 0–1 比率。

### Fresh Self-Review

由同一执行 Agent 从 diff 和测试结果进行复查，不称为独立评审。检查点：旧字段保留、无契约变更、目标对象独立授权、无越权来源读取、竞态失效、上下文保留、手机尺寸和安全文本插值。未发现本批次遗留阻断问题；与已批准范围无规格冲突。

### 尚未实现

阶段 2–6 尚未完成：反馈接收人及受理、需求环节人员与新流程、可操作进度区、版本批量关联、邮件投递和旧数据迁移。当前摘要暂展示现有需求信息，人员和精简进度将在后续对应阶段接入。本批次完成不代表整个优化方案或发布候选已完成。

## 阶段 2 接收人与环节人员基础

2026-10-31 用户明确要求阶段通过后直接继续，不逐次等待确认。本阶段代码提交 f4d0818，通过本地门禁后进入阶段 3。

- 开发契约先行增加人员候选、反馈接收人修改／转交、环节人员读取／修改；同步类型与受保护中文接口文档。
- 0005 migration 增加受理字段、接收关系、参与关系与持久事件；历史确认信息保持空，有协作数据时拒绝破坏性 downgrade。
- 反馈接收人须有原有读取资格；受理 CAS 保证单人成功，转交保留原受理事实。
- Requirement SELF 范围增加有效参与人，保留原 owner 读取依据；移出成员不再因参与关系可见。
- 前端接入搜索分页人员选择、接收与转交面板、环节人员面板，新建反馈界面至少选一人。
- 过渡兼容：旧 API 客户端省略 recipient_ids 仍能创建历史形式反馈；显式列表不能为空或含无资格人员。阶段 6 需确认兼容口径，不能声称本阶段所有 API 新建均强制接收人。
- 业务事务内持久保存事件，消费及邮件发送在阶段 5 实现。

实际门禁：后端 378 passed / 1 skipped（未配置 S3）；PostgreSQL 专项 40 passed / 0 skipped；前端 49 文件、331 passed；Ruff、Mypy、构建、类型和 bundle 检查通过。新增测试验证无资格人员失败无残留、并发受理单一胜者、转交保留受理人、参与范围增减、旧 owner 读取、前端冲突不自动重放及账号切换失效旧响应。

仅使用本任务独立 Docker 容器 iterflow-workflow-test-db（127.0.0.1:32768）和 iterflow-workflow-test-redis（127.0.0.1:32769）。upgrade head、alembic check 和隔离旧迁移往返测试通过，没有连接或修改真实数据库。旧测试夹具补入新增依赖表，已发布契约冻结改为校验 v1.8.1 文件摘要，开发契约继续完整 runtime parity。

修改文件范围：collaboration schemas／service／router，反馈 service，需求 repository，entities 和 0005 migration，对应后端测试和文档资源，前端 collaboration API、PeopleSelector、CollaborationPeople、反馈与需求详情、生成类型及组件测试。Fresh Self-Review 属于同一 Agent 自查，检查权限、CAS、旧字段与事务边界。未部署、未执行真实数据库操作或远端 CI。后续新状态流程、批量关联和邮件尚未完成。
