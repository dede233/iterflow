# 状态机

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
