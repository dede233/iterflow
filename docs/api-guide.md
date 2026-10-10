# IterFlow 当前接口集成指南

更新日期：2026-10-10。对应未发布开发契约 `spec/openapi-development.yaml` 和本地协作分支，线上是否支持新增接口须先核对部署版本。历史发布契约保持不变；本指南不构成上线验收。用户操作见 [操作手册](user-manual.md)。

## 访问和权限

业务路径以 `/api/v1` 为前缀，使用登录获得的 Bearer Access Token。刷新及登出按 Auth 契约执行，不把 Token 写入 URL 或日志。首次改密受限账号先完成改密。

受保护文档为 `GET /api/v1/docs/openapi`，桌面系统设置、手机我的中可进入并搜索、下载。仅启用的系统 `SUPER_ADMIN` 或 `DEVELOPMENT_LEAD` 可读；普通开发、设计、产品以及自定义同名角色不能代替。生产公共 Swagger/OpenAPI 关闭。读取文档会记审计，响应 private/no-store。

业务接口分别检查权限码及 DataScope。SELF 下开发、设计参与关系提供需求可见性，不自动授予权限，也不自动扩展版本范围。开始阶段需同时 `rd.requirement.edit`、`rd.requirement.status`；产品基础角色仅有前者，按实际职责配置角色组合。

## 阶段和人员接口

以下路径省略 `/api/v1`。每次写操作读取最新 revision，成功后以响应的 revision 继续；人员确认也会改变需求 revision。

| 方法与路径 | 用途与门禁 |
| --- | --- |
| GET /requirements/assignee-options | 需求编辑权限；kind OWNER/DEVELOPER/DESIGNER，支持 keyword 和分页；只返回可分配人员摘要 |
| GET /requirements/{id}/collaborators | 需求查看与范围；返回 owner、developers、designers、development_completions、revision |
| POST /requirements/{id}/start-stage | 编辑与状态权限、范围；PLANNED 到 DESIGNING/DEVELOPING，或 DESIGNING 到 DEVELOPING；只分配当前阶段人员 |
| PATCH /requirements/{id}/collaborators | 编辑权限、范围；kind OWNER/DEVELOPMENT/DESIGN，只改指定职责 |
| PUT /requirements/{id}/collaborators | 编辑权限、范围；兼容的完整分工替换，必须提交全部字段，不宜用于单组调整 |
| POST /requirements/{id}/development-completion | 当前绑定开发人员本人；查看和状态权限、范围；仅 DEVELOPING/TESTING/DONE |
| PATCH /requirements/{id}/status | 状态权限、范围；集中状态机与完成门禁 |

开始阶段的请求示例，ID 与 revision 仅为格式示例，执行时取当前环境有效值：

```json
{"revision": 8, "status": "DESIGNING", "user_ids": [21, 22]}
```

开发阶段用 `status: DEVELOPING` 和开发人员 ID。每阶段 1–100 人，不允许重复；人员必须启用、有需求查看权限，并有设计或开发资格。阶段开始的关联、状态、CAS、审计、通知原子提交。设计进入开发后保留设计分工。

单独调整人员示例：

```json
{"revision": 9, "kind": "DEVELOPMENT", "user_ids": [31, 32]}
```

总负责人使用 `kind: OWNER`、`owner_id`；设计分工使用 `kind: DESIGN`。设计分工仅设计中调整，开发分工可在开发、测试、完成阶段调整；对应阶段不允许清空名单。完整 PUT 仍保留，但当前前端优先单组 PATCH。

本人确认请求只有 revision，不接受用于代确认的额外字段：

```json
{"revision": 10}
```

确认身份来自登录用户。开发候选及确认资格为启用 DEVELOPER 或 DEVELOPMENT_LEAD，不允许管理员代确认。响应的 `development_completions` 每项含 `user_id` 与可空 `completed_at`；空时间表示未确认。

每次进入 DEVELOPING 清空所有确认。保留未移除人员的确认，新增或移除后再次加入的人员待确认。全员确认不会自动 DONE；进入 DONE 必须至少一名开发且全部本人确认。调整已完成需求的开发名单可能重新阻断发布。

## 状态与兼容边界

需求主流程为 DRAFT → CONFIRMED → PLANNED → 可选 DESIGNING → DEVELOPING → TESTING → DONE → ONLINE。DONE → DEVELOPING 仅所属版本未发布且有非空 reason 时允许。ONLINE 仅由成功发布事务产生。

历史普通状态 API 的 PLANNED → DEVELOPING 保持兼容，不强制已有客户端提交阶段名单；当前前端使用 start-stage。即使通过旧入口进入开发，DONE 与发布仍检查非空开发名单及全部确认。普通状态进入 DESIGNING，或 DESIGNING → DEVELOPING，要求已有对应分工。完整状态规则见 [状态机](../spec/status-machines.md)。

反馈 ACCEPTED 不必 reason；DUPLICATE 必须 duplicate_of_id（可见、非自身），不必 reason；CANNOT_REPRODUCE、CLOSED 和重开 NEW 必须非空 reason。CLOSED 编辑保存仍 CLOSED，另调状态 API 重开保留 ID 与历史。REQUIREMENT_LINKED/ONLINE 禁止人工设置。

Version READY → TESTING 需要 reason；RELEASED 只能 publish 产生。READY/RELEASED/CANCELED 的需求清单冻结；基础信息 PATCH 仍允许在已发布状态修改 name、owner_id、planned_release_date、description，受编辑权限、范围、CAS 与审计保护。不允许修改 version_no、状态、关联清单或已有 Release 字段。

## 发布与并发错误

`POST /versions/{id}/publish/check` 与实际 `POST /versions/{id}/publish` 使用相同前置规则：版本 READY，全部有效需求 DONE，各需求至少一名开发并全员本人确认，操作者发布权限及范围满足。检查响应包含 `DEVELOPMENT_COMPLETION_CHECK`，不通过返回 409 及 checks。

实际发布重新校验并锁定相关业务行；Release SUCCESS、Version RELEASED、有效需求与关联反馈 ONLINE、通知及审计同一事务提交。中途失败全部回滚。重复发布冲突，不制造多条成功 Release；检查成功不保证稍后发布一定成功。

旧 revision 返回 HTTP 409、业务码 40910；完成条件不满足返回 HTTP 409、业务码 40913。不同冲突应按响应业务码及 details 处理，不能把所有 409 都当成旧 revision 或自动重试。刷新最新对象、保留用户输入并明确解决冲突；失败时不能更新本地 revision 假装成功。

401 需重新认证，403 权限或首次改密限制，404 对象不存在或不在范围，422 参数不符合契约。时间使用 ISO 8601，数据库 UTC；日期筛选按端点约定，前端显示本地时区。文件元数据使用 file_id，下载与删除由后端验证授权，不暴露物理存储路径。

## 契约和文档同步

先修改当前开发契约，保持字段、类型、必填、枚举与实现一致。只修改说明时不改 API shape；历史已发布快照、tag 和 Release 不重写。生成工具保留契约的 summary/description 等说明，受保护文档包随应用构建交付。

```bash
# 仓库根目录；使用项目虚拟环境
cd backend
../.venv/bin/python -m scripts.sync_openapi
../.venv/bin/python -m scripts.build_api_documentation
cd ../frontend
npm run generate:api-types
npm run check:api-types
npm run build
npm run check:bundle
```

同步后运行后端契约与文档访问测试、前端文档测试，并验证受保护 API 返回与下载一致。文档元数据被进程缓存，重新启动自己负责的本地 API 才能验证更新；不要误重启其他环境。

Word 手册由 `tools/build-user-manual.py` 从 `docs/user-manual.md` 生成，再通过 DOCX 渲染工具检查每页并导出 PDF。修改手册正文时应重新生成两种交付文件。

当前协作迁移为 PostgreSQL `0007_development_completion` / MySQL `mysql57_0005`。既有库用相应 Alembic upgrade head 升级，不重复 seed；MySQL 正式迁移后执行 mysql_preflight。新增功能尚需新 CI、部署包验收、受保护的升级前备份和授权部署，不能用文档同步替代这些门禁。
