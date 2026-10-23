# 三类角色完整版本权限：合并与部署记录

2026-10-23 用户授权合并并推送，先更新保留的 8444 测试环境做多账号验收，通过后再更新 8443 正式环境。账号、业务数据和附件保留，不执行 seed、restore、删除卷或创建 tag/Release。

## 合并与源产物

源分支 `codex/version-role-permissions` 的最终提交为 `6fd4f3f895dc86944d78a4a1f0bee9e88929104d`，八项 CI [39896249803](https://github.com/dede233/iterflow/actions/runs/39896249803) 全部通过。
核对 GitHub/Gitee master 均为 `f98fff1f87c477c5f12194614d108e0ea4e2938c` 后 no-ff 合并为 `198f831d67e8b475975915b1824d711b949fb998`，双远端推送成功，产品树与源分支一致。合并 master 八项 CI [39897074823](https://github.com/dede233/iterflow/actions/runs/39897074823) 全部通过，含两种真实 MySQL 5.7 配置、PostgreSQL、浏览器、Docker、备份恢复和 S3。

冻结该合并提交构建 linux/amd64 API/Web，离线包保存于 `/Users/xiaweiyi/Developer/deliverables/iterflow/2026-10-23/version-role-198f831-linux-amd64.tar.gz`，276563878 bytes，SHA256 `b5b86fb03ea501811f1ecc42fe8796369c5e4848847630fbe70cf7a2a00c189b`。包含 API、Web 及原 Redis/MySQL 客户端镜像，不包含真实配置、账号、附件或数据库内容。镜像配置摘要与层清单见 `evidence/version-role-permissions/image-identities.json`。

第一次构建误用系统旧 Python，在解包参数检查处失败，尚未构建；改用项目 Python 3.12 后完成。原失败日志保留，未修改构建要求。

## 升级校验与当前状态

随本记录保留一次性升级与验收脚本，固定目标源提交、测试项目及数据库；没有自动清理或自动降级恢复。脚本先停写并备份数据库和附件，再追加 `mysql57_0005 -> mysql57_0006`，仅允许三类角色的缺失授权、revision、更新时间、迁移审计与 Alembic head 变化；其他表与附件须逐项摘要一致。更新后验证健康、实际镜像身份和 API/Web 顺序重启，保留数据库、Redis、挂载、restart 策略及原 80/443 配置。

测试使用三类纯角色账号与既有开发、成员、设计、测试账号，经真实 Web/API 执行版本创建编辑、安排/迁移/移出/重加、状态推进、发布检查和发布，并核对全员确认门禁、CAS409、越界404、无权403、历史关系、上线同步、通知和审计。仅在 `iterflow_acceptance` 创建合成记录。正式环境以只读页面、健康和数据保全验收，不创建测试记录。

本提交时：合并和构建已完成，离线包正在上传，测试与正式环境尚未更新。后续实际执行结果在本文件追加；不得将预备脚本或计划视为部署成功证据。
