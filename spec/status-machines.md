# 状态机

## Requirement
DRAFT -> CONFIRMED -> PLANNED -> DEVELOPING -> TESTING -> DONE -> ONLINE

旁路：CONFIRMED/PLANNED/DEVELOPING/TESTING 可进入 PAUSED；DRAFT/CONFIRMED/PLANNED/PAUSED 可按规则取消。

## Version
PLANNING -> DEVELOPING -> TESTING -> READY -> RELEASED

RELEASED 为终态。发布必须通过独立事务执行 Release + Version + Requirement + Feedback + Notification 同步。

## Concurrency
关键对象写操作必须提交 `revision`。旧 revision 写入返回 HTTP 409，禁止静默覆盖。
