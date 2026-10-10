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
DRAFT -> CONFIRMED -> PLANNED -> [DESIGNING] -> DEVELOPING -> TESTING -> DONE -> ONLINE

2026-10-10 用户授权增加可选设计阶段：PLANNED 可进入 DESIGNING，也可直接进入 DEVELOPING。
DESIGNING 可进入 DEVELOPING、PAUSED、CANCELED；PAUSED 允许恢复 DESIGNING。

开始设计/开发使用 `POST /requirements/{id}/start-stage`，仅具备需求编辑和状态权限且数据范围可见的操作者可执行。
该接口要求至少一名对应角色的启用参与人员，人员分工、状态、一次 revision CAS、审计和定向站内通知原子提交。
设计阶段开始时选择设计人员，开发阶段开始时选择开发人员；设计分工在开发后保留。
普通状态接口进入 DESIGNING，或从 DESIGNING 进入 DEVELOPING 时，也必须已有对应分工。
既有 PLANNED -> DEVELOPING 普通状态 API 保持兼容，不强制改写历史需求或已有客户端；新前端使用阶段接口选择人员。

旁路：CONFIRMED/PLANNED/DESIGNING/DEVELOPING/TESTING 可进入 PAUSED；DRAFT/CONFIRMED/PLANNED/DESIGNING/PAUSED 可按规则取消。

- `ONLINE` 只能由成功发布事务自动产生，普通状态接口禁止设置。
- `DONE -> DEVELOPING` 仅在所属 Version 尚未发布时允许，必须填写原因并写审计日志。

2026-10-10 用户授权全员开发完成确认，并进一步要求未全员确认时不能标记需求完成：进入 DONE 必须至少有一名开发人员且全部已本人确认，否则返回 409，事务不提交。提测仍按原流程；全员确认不会自动将需求置为 DONE。
开发、测试、完成阶段，绑定的启用且具备开发资格的人员可确认本人完成；总负责人/管理员不能代确认。
每次进入 DEVELOPING（包括恢复开发、退回开发）清空全部既有确认，并写审计；新增或移除后再加入的人员待确认。
未变更分工的人员确认保留；禁止用空开发名单绕过门禁。既有需求不自动确认。
Version 发布要求每条有效关联需求至少一名开发人员，且全部本人确认完成；原 READY、DONE、权限门禁仍然成立。
详见 `docs/development-completion.md`。

## Version
PLANNING -> DEVELOPING -> TESTING -> READY -> RELEASED

- `RELEASED` 只能通过 `POST /versions/{id}/publish` 进入，普通状态接口禁止设置。
- `READY -> TESTING` 允许退回，但必须填写原因并写审计日志。
- V1.5 MVP 仅支持成功发布；发布固定生成 `Release.result = SUCCESS`。
- `RELEASED` 为终态。发布必须通过独立事务执行 Release + Version + Requirement + Feedback + Notification 同步。
- 终态限制状态与有效需求清单；当前版本基础信息编辑仍允许修改名称、负责人、计划日期、描述，须权限、范围、revision CAS 与审计。已有 Release 记录不被此编辑改写。用户操作见 `docs/user-manual.md`。

## Concurrency
关键对象写操作必须提交 `revision`。旧 revision 写入返回 HTTP 409，禁止静默覆盖。
