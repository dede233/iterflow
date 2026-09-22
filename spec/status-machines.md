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
- `DUPLICATE / REQUIREMENT_LINKED / ONLINE` 等非人工状态禁止人工设置；请求体使用 `ManualFeedbackStatus`，因此提交这些值直接 422。
- `REQUIREMENT_LINKED` 仅由 Feedback→Requirement 转换事务产生（Phase 4）。
- `ONLINE` 只能由 Version 成功发布事务自动产生，普通状态接口任何情况下都不能设置。
- 所有写操作提交 `revision`，旧 `revision` 返回 409（乐观锁，禁止静默覆盖）。

## Requirement
DRAFT -> CONFIRMED -> PLANNED -> DEVELOPING -> TESTING -> DONE -> ONLINE

旁路：CONFIRMED/PLANNED/DEVELOPING/TESTING 可进入 PAUSED；DRAFT/CONFIRMED/PLANNED/PAUSED 可按规则取消。

- `ONLINE` 只能由成功发布事务自动产生，普通状态接口禁止设置。
- `DONE -> DEVELOPING` 仅在所属 Version 尚未发布时允许，必须填写原因并写审计日志。

## Version
PLANNING -> DEVELOPING -> TESTING -> READY -> RELEASED

- `RELEASED` 只能通过 `POST /versions/{id}/publish` 进入，普通状态接口禁止设置。
- `READY -> TESTING` 允许退回，但必须填写原因并写审计日志。
- V1.5 MVP 仅支持成功发布；发布固定生成 `Release.result = SUCCESS`。
- `RELEASED` 为终态。发布必须通过独立事务执行 Release + Version + Requirement + Feedback + Notification 同步。

## Concurrency
关键对象写操作必须提交 `revision`。旧 revision 写入返回 HTTP 409，禁止静默覆盖。
