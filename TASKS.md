# TASKS.md

# V1.5 实际开发执行清单

> 规则：按阶段完成。除非存在明确依赖调整，不要跳过前置阶段。
> 每个阶段完成后必须运行测试并输出阶段报告。

## Phase 0 — 工程体检与启动基线

- [ ] 阅读 `AGENTS.md`
- [ ] 阅读 V1.5 主文档
- [ ] 阅读 OpenAPI
- [ ] 阅读状态机
- [ ] 检查 backend 依赖
- [ ] 检查 frontend 依赖
- [ ] 检查 Docker Compose
- [ ] 检查 Alembic
- [ ] 列出“缺失实现 / 占位实现 / 规格冲突”
- [ ] 确保 Python 工程可导入/编译
- [ ] 确保 Frontend 可构建
- [ ] 确保基础设施容器可启动

### Phase 0 验收
- [ ] `/health` 返回成功
- [ ] PostgreSQL 可连接
- [ ] Redis 可连接
- [ ] MinIO 可连接
- [ ] 前端构建通过

---

## Phase 1 — 数据库与基础系统

- [ ] 完成/校正 SQLAlchemy Model
- [ ] 完成 Alembic initial migration
- [ ] User
- [ ] Role
- [ ] Permission
- [ ] UserRole
- [ ] RolePermission
- [ ] System/Module dictionary
- [ ] AuditLog
- [ ] File metadata
- [ ] Notification
- [ ] 索引/唯一约束
- [ ] revision 字段

### Phase 1 验收
- [ ] 空库 migration upgrade 成功
- [ ] seed 成功
- [ ] 默认管理员创建成功
- [ ] 默认角色/权限创建成功
- [ ] downgrade/upgrade 基础验证通过

---

## Phase 2 — Auth + RBAC

- [ ] 登录
- [ ] Refresh Token
- [ ] 退出/撤销会话
- [ ] 修改密码
- [ ] 首次登录强制改密
- [ ] 用户启停
- [ ] 角色管理
- [ ] 权限分配
- [ ] 后端权限依赖
- [ ] 数据范围 SELF / TEAM / ALL
- [ ] 前端登录态
- [ ] 路由权限
- [ ] 按钮权限

### Phase 2 验收
- [ ] 正确账号可登录
- [ ] 错误密码失败
- [ ] Disabled 用户拒绝登录
- [ ] 无权限 API 返回 403
- [ ] 隐藏按钮与后端 403 同时成立
- [ ] Access Token 过期后 Refresh 正常

---

## Phase 3 — Feedback

- [ ] Feedback 列表
- [ ] Feedback 详情
- [ ] 提交 Feedback
- [ ] 编辑 Feedback + revision
- [ ] 状态变化
- [ ] 受理
- [ ] 标记重复
- [ ] 无法复现
- [ ] 关闭/重开
- [ ] 附件
- [ ] 评论
- [ ] 审计日志
- [ ] PC 页面
- [ ] Mobile 页面

### Phase 3 验收
- [ ] 新反馈编号唯一
- [ ] 普通用户可看自身范围数据
- [ ] 过期 revision 更新返回 409
- [ ] 所有状态操作可审计
- [ ] 移动端能提交附件反馈

---

## Phase 4 — Requirement

- [ ] 直接新建 Requirement
- [ ] Feedback -> Requirement
- [ ] 关联已有 Requirement
- [ ] 多 Feedback 合并
- [ ] Requirement 列表
- [ ] Requirement 详情
- [ ] 状态机
- [ ] 优先级
- [ ] 负责人
- [ ] 验收标准
- [ ] revision
- [ ] Redis 编辑提示
- [ ] 冲突界面
- [ ] 操作日志
- [ ] PC 页面
- [ ] Mobile 页面

### Phase 4 验收
- [ ] 一个 Feedback 只有一个主 Requirement
- [ ] 一个 Requirement 可关联多个 Feedback
- [ ] 非法状态迁移返回 409
- [ ] 两人打开同一需求，后保存旧 revision 的用户收到 409
- [ ] 409 后可查看最新 revision/更新人
- [ ] 不发生静默覆盖

---

## Phase 5 — Version

- [ ] Version 列表
- [ ] Version 创建/编辑
- [ ] Version 状态机
- [ ] 添加直接 Requirement
- [ ] 从 Feedback 池加入
- [ ] 需求移出版本
- [ ] 需求跨版本迁移
- [ ] 迁移原因
- [ ] active VersionRequirement 唯一约束
- [ ] Version 详情进度统计
- [ ] PC 页面
- [ ] Mobile 页面

### Phase 5 验收
建立 V1.0.1：
- [ ] A Requirement 直接新建并加入
- [ ] B Requirement 直接新建并加入
- [ ] C Requirement 由 Feedback 转入并加入
- [ ] A/B/C 在 Version 内同级
- [ ] C 可追溯原始 Feedback
- [ ] 需求迁移到 V1.0.2 后历史仍保留

---

## Phase 6 — Release

- [ ] READY 状态校验
- [ ] 发布前阻塞项校验
- [ ] 创建 Release
- [ ] Version -> RELEASED
- [ ] 完成需求 -> ONLINE
- [ ] 关联 Feedback -> ONLINE
- [ ] 发布通知
- [ ] 发布审计
- [ ] 事务回滚
- [ ] Release 历史页面

### Phase 6 验收
- [ ] 发布事务完整成功
- [ ] 人为制造中途异常时整个事务回滚
- [ ] Release 记录存在
- [ ] Requirement / Feedback 同步正确
- [ ] 提交人收到通知

---

## Phase 7 — Notification / File / Audit 完善

- [ ] 通知列表
- [ ] 未读计数
- [ ] 标记已读
- [ ] 业务跳转
- [ ] MinIO 上传
- [ ] 文件 MIME/扩展名校验
- [ ] 签名下载
- [ ] SHA-256
- [ ] 审计检索
- [ ] 操作前后值
- [ ] 关键管理操作审计

### Phase 7 验收
- [ ] 无权限用户不能下载无权访问附件
- [ ] 可执行文件被拒绝
- [ ] 通知跳转到正确业务对象
- [ ] 审计能追踪核心状态变化

---

## Phase 8 — Dashboard + System

- [ ] 首页核心指标
- [ ] 待处理反馈
- [ ] 进行中需求
- [ ] 当前版本
- [ ] 累计发布
- [ ] 最近动态
- [ ] 系统字典
- [ ] 系统/模块配置
- [ ] 账号/角色管理 UI
- [ ] 审计页面

### Phase 8 验收
- [ ] 指标与数据库统计一致
- [ ] 移动端首页信息可读
- [ ] 系统字典变更可审计

---

## Phase 9 — 响应式与体验验收

- [ ] Desktop >= 1200
- [ ] Tablet 768–1199
- [ ] Mobile < 768
- [ ] 桌面表格 -> 手机卡片
- [ ] 筛选栏 -> 手机 Drawer
- [ ] Dialog -> 手机全屏交互
- [ ] Tabs 可滚动
- [ ] 操作按钮触摸区域
- [ ] 上传/预览移动端正常
- [ ] 409 冲突移动端正常

### Phase 9 验收
至少检查：
- [ ] 375px
- [ ] 390px
- [ ] 768px
- [ ] 1280px
- [ ] 1440px

---

## Phase 10 — 自动化、部署与最终验收

- [ ] Backend pytest
- [ ] 权限测试
- [ ] 状态机测试
- [ ] 并发冲突测试
- [ ] 发布事务测试
- [ ] Frontend build
- [ ] Docker build
- [ ] docker compose 一键启动
- [ ] migration 自动执行策略确认
- [ ] health/readiness
- [ ] 数据库备份策略
- [ ] 对象存储备份策略
- [ ] 默认密码安全检查
- [ ] README 更新

## 最终 E2E

必须实际跑通并记录：

`管理员登录`
-> `创建/授权成员`
-> `成员提交 FB-xxxxx`
-> `负责人受理`
-> `反馈转 REQ-xxxxx`
-> `设置负责人/优先级`
-> `加入 V1.0.1`
-> `状态流转到 DONE`
-> `版本到 READY`
-> `发布`
-> `生成 Release`
-> `REQ ONLINE`
-> `Feedback ONLINE`
-> `通知到提交人`
-> `审计链路完整`

并额外执行多人冲突：

- Agent/User A 与 B 同时读取同一个 Requirement revision=N
- A 保存成功 revision=N+1
- B 使用 N 保存
- B 必须收到 HTTP 409
- A 的修改不得被 B 覆盖

### 完成定义（Definition of Done）

只有同时满足以下条件才可宣告项目 MVP 完成：

- [ ] 主链路真实可操作
- [ ] 权限不能绕过
- [ ] revision 冲突真实生效
- [ ] 状态机真实生效
- [ ] 发布事务真实生效
- [ ] PC 核心页面可用
- [ ] Mobile 核心页面可用
- [ ] 自动化测试通过
- [ ] Docker 一键启动
- [ ] 无默认弱密码
- [ ] 文档与 OpenAPI 已同步
