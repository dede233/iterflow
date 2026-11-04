# 状态机

## Feedback

完整状态：`NEW, ACCEPTED, REQUIREMENT_LINKED, ONLINE, DUPLICATE, CANNOT_REPRODUCE, CLOSED`

人工可设置状态（`ManualFeedbackStatus`，经 `PATCH /feedbacks/{id}/status`）：`NEW, ACCEPTED, DUPLICATE, CANNOT_REPRODUCE, CLOSED`

合法人工迁移（其余一律 HTTP 409）：

```
NEW       -> ACCEPTED
NEW       -> DUPLICATE          (需 duplicate_of_id)
ACCEPTED  -> DUPLICATE          (需 duplicate_of_id)
NEW       -> CANNOT_REPRODUCE   (需 reason)
ACCEPTED  -> CANNOT_REPRODUCE   (需 reason)
NEW       -> CLOSED             (需 reason)
ACCEPTED  -> CLOSED             (需 reason)
DUPLICATE         -> NEW        (重开; 需 reason; 清空 duplicate_of_id)
CANNOT_REPRODUCE  -> NEW        (重开; 需 reason)
CLOSED            -> NEW        (重开; 需 reason)
```

- `ACCEPTED -> NEW` 明确不允许。
- `reason`（trim 后非空）在 `-> CANNOT_REPRODUCE`、`-> CLOSED` 与所有重开（`-> NEW`）时必填；仅保存在 `STATUS_CHANGE` 审计中，不新增数据列。
- `-> DUPLICATE` 时 `duplicate_of_id` 必填，须为存在、非自身、且操作者数据范围内可见的 Feedback。
- Feedback 是外部输入记录，不承担研发状态机；不得出现或同步 `PLANNED / DEVELOPING / TESTING`。
- `REQUIREMENT_LINKED / ONLINE` 事务产出状态禁止人工设置；请求体使用 `ManualFeedbackStatus`，因此提交这些值直接 422。
- `REQUIREMENT_LINKED` 仅由 Feedback→Requirement 转换事务产生（Phase 4）。
- `ONLINE` 只能由 Version 成功发布事务自动产生，普通状态接口任何情况下都不能设置。
- 所有写操作提交 `revision`，旧 `revision` 返回 409（乐观锁，禁止静默覆盖）。

## Requirement
DRAFT（待确认） -> CONFIRMED（待开发） -> DEVELOPING（开发中） -> TESTING（待验收） -> DONE（待发布） -> ONLINE（已上线）

2026-10-31 授权的新工作流：PLANNED 仅保留历史读取枚举，迁移为 CONFIRMED，不再接受人工写入。直接创建／反馈转新需求从 DRAFT 开始；加入版本不改变需求状态。确认、开始开发、提验、验收分别由具备权限的对应环节人员操作；人员分配不等于确认。修改 description／acceptance_criteria 增加内容版本，旧确认失效，继续正向流转或发布前须确认当前内容。设计为可选子进度，启用后提验前须完成或有原因取消。

待验收退回开发、暂停、恢复、取消均记录原因；暂停恢复目标只允许 CONFIRMED／DEVELOPING。2026-11-04 Issue #4 增量允许 CANCELED 经 workflow REOPEN 返回 DRAFT：原因必填，所属版本已发布则拒绝，清除当前确认资格和暂停来源，保留人员、关联与真实历史；ONLINE 不可重开。历史已完成需求保留发布资格，缺失的确认人和时间不得伪造。发布前检查与正式发布均检查当前内容确认资格。

旁路：CONFIRMED/DEVELOPING/TESTING 可进入 PAUSED；DRAFT/CONFIRMED/PAUSED 可按规则取消。

- `ONLINE` 只能由成功发布事务自动产生，普通状态接口禁止设置。
- `DONE -> DEVELOPING` 仅在所属 Version 尚未发布时允许，必须填写原因并写审计日志。

2026-10-31 用户明确选择新方案：取消逐人开发完成确认。任一有权限的开发参与人可提交验收，指定验收人确认 DONE；原开发确认接口下线，原确认时间保留历史表与迁移步骤快照，不再参与 DONE/发布门禁。主状态 PLANNED/DESIGNING 都映射到 CONFIRMED，原 DESIGNING 保留为 IN_PROGRESS 设计子进度；不伪造确认/验收人员。

## Version
2026-11-04 用户批准：版本进度由有效关联需求自动汇总，人工仅取消或正式发布；不再手动推进开发/测试/READY或退回版本阶段。API有效状态仍使用原枚举，历史非终态存储保持读取兼容但不是当前进度来源。

- 空清单为PLANNING；全部DONE且内容确认有效为READY；全TESTING/DONE但未就绪为TESTING；已开始工作但混有其他未完成项为DEVELOPING；其余为PLANNING。PAUSED/CANCELED需求不被静默忽略，异常ONLINE需求不取得发布资格。
- 全局进度、列表筛选及统计采用同一只读派生规则，不触发数据库写入。原RELEASED/CANCELED终态保持。
- READY为可发布提示，允许通过原权限、双revision和审计的清单接口继续调整；仅RELEASED/CANCELED冻结。调整后重新汇总。

- `RELEASED` 只能通过 `POST /versions/{id}/publish` 进入，普通状态接口禁止设置。
- 旧手动版本阶段接口仅接受取消未发布版本；推进或退回阶段返回409并引导操作需求。
- V1.5 MVP 仅支持成功发布；发布固定生成 `Release.result = SUCCESS`。
- `RELEASED` 为终态。发布必须通过独立事务执行 Release + Version + Requirement + Feedback + Notification 同步。
- 终态限制状态与有效需求清单；当前版本基础信息编辑仍允许修改名称、负责人、计划日期、描述，须权限、范围、revision CAS 与审计。已有 Release 记录不被此编辑改写。用户操作见 `docs/user-manual.md`。

## Concurrency
关键对象写操作必须提交 `revision`。旧 revision 写入返回 HTTP 409，禁止静默覆盖。

## 2026-11-02 多人验收与确认后安排人员

- ACCEPT 可指定多人，任意一名有权限的有效验收人员通过即可 TESTING → DONE，不进行逐人会签；退回仍须原因。2026-11-04 Issue #4 将 CONFIRM 同样扩展为多人、任意一名有效且有权限的确认人确认即可；本节下述单CONFIRM迁移约束为历史基线。
- 提交验收通知所有验收人员，邮件遵循验证与偏好；确认记录保留实际操作者和当时人员快照。并发或重复确认不得重复推进状态、写记录或发通知，旧 revision 返回 409。
- 本人确认成功从 DRAFT 进入 CONFIRMED 后，具备人员编辑权限的操作者自动看到人员选择弹窗。关闭不撤销确认，保存人员不代表开始开发；后续重新确认不改变已有阶段。
- 追加 0012_multiple_acceptance / mysql57_0010 仅放开 ACCEPT 唯一约束，保留 CONFIRM 唯一约束及全部历史行；已有单人验收无需补写。存在多人有效验收时拒绝降级，不自动删人。MySQL DDL 升级需停止写入并备份；本次仅隔离验证。

## 2026-11-04 Issue #4

- CONFIRM 单人数据库约束由追加迁移 0014_issue4 / mysql57_0012 取消；旧参与人行及快照保留。并发确认仍只有一个 revision 成功，不重复记录和通知。
- 需求描述明确 PLAIN/HTML 格式；旧数据默认 PLAIN，HTML 经白名单清洗。修改内容格式也使当前确认失效。标题、描述不能保存为空白或仅不可见内容，创建、编辑和反馈转需求均校验。
- 软删除仅允许 NEW 反馈、DRAFT 需求，且没有需求/反馈/版本/重复记录关联或历史引用；原因必填，现有编辑权限和 DataScope、revision、审计继续生效。删除保留实体行与历史，普通读取、统计和新关联排除，不增加实体状态枚举。
- 批量需求动作支持确认、CONFIRMED→DEVELOPING、DEVELOPING→TESTING、TESTING→DONE；反馈支持NEW→ACCEPTED及NEW/ACCEPTED→CLOSED。逐项执行原门禁与事务，返回成功或失败明细，最多50条，不批量发布或自动重试。
