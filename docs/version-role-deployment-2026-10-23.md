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

准备提交 d885b01 时，合并和构建已完成，双环境尚未更新；以下为后续真实执行结果。


## 双环境部署结果

2026-10-23 12:12（北京时间）测试升级验证完成，随后完成真实多账号验收；12:19 正式升级验证完成。两端均运行合并源 `198f831` 的同一批 linux/amd64 镜像，数据库 head 为 `mysql57_0006`。证据位于 [deployed](evidence/version-role-permissions/deployed/)，正式与测试各追加 8 条缺失角色授权和 3 条迁移审计；三个目标角色 revision 增加，其他表逐行摘要与附件摘要保持一致。未重跑 seed，未创建正式测试账号或业务记录。

- 测试：https://sx-kc.xyz:8444 ，独立 MySQL 5.7.44-log；正式：https://sx-kc.xyz:8443 ，RDS MySQL 5.7.44-log。两者沿用 portable OFF/OFF 配置。
- API 镜像 `iterflow-api:mysql57-198f831d67e8`，配置摘要 `sha256:d02e7f8236b8deeac8f3fe91b1a7bf01f1e7da32d10a85bbb1ffcf6912cbd09e`。
- Web 镜像 `iterflow-web:mysql57-198f831d67e8`，配置摘要 `sha256:58b9fae5b662031c4b5f15aad9cc1412ff3ab7f76777af80b2557457982022f9`。
- API/Web 顺序停止、启动、健康、HTTPS 以及持久卷核对通过。保留现有 Redis、测试数据库与 80/443 站点；Docker、测试栈和测试 Nginx 自动恢复服务均 enabled/active，容器仍为 unless-stopped。本轮没有重启整台服务器。
- 更新维护控制器的源 SHA 与正式基线，旧文件备份在服务器证据目录，保留 `retention.keep` 与 `cleanup_hold`。测试账号和合成验收记录继续保留。

## 多账号验收

测试库通过真实部署的 HTTP Web/API 完成三次实际发布：ceshi014（开发）、ceshi015（产品负责人）、ceshi016（研发负责人），对应版本 11/13/15。覆盖创建编辑、安排/迁移/移出/重加、合法历史、状态推进、0/2 与 1/2 开发确认拦截、本人确认、DONE、发布检查、旧 revision 409、成功发布及重复发布 409、唯一 Release、需求/反馈上线、提交人通知与实际发布者审计。SELF 越界返回 404，产品原 ALL 范围保留，成员/设计/测试角色无权调用返回 403。首次改密也已验证。

真实 HTTPS Playwright 页面验收 6/6 通过、0 跳过、无 mock，覆盖三类角色的页面创建/编辑/推进/发布检查、三类无权角色的按钮与路由拦截，以及 375/390/768/1280/1440 五种宽度。页面测试不点击最终发布；实际发布由上述 HTTP 验收完成。中途异常回滚测试使用本地及 CI 证据，本轮没有向远程在线业务事务注入异常。

## 备份与失败记录

四组数据库及附件备份均保存在服务器 `/opt/iterflow/backups/`，未下载数据库或附件内容：

| 环境 | 升级前目录 | 升级后目录 |
| --- | --- | --- |
| 测试 | version-roles-test-pre-20261023T040750Z | version-roles-test-post-20261023T040802Z |
| 正式 | version-roles-production-pre-20261023T041714Z | version-roles-production-post-20261023T041749Z |

每个文件的 SHA256 见对应 upgrade.json。测试后备份是在迁移后、合成业务验收前生成，不能称为包含全部验收记录的备份。本轮未执行远程恢复。

测试升级第一次因运行账号无 TRIGGER 元数据可见性而被拦截，数据库仍是 0005；改为使用迁移账号只读快照后确认 73 个触发器，未追加数据库权限。第二次已完成迁移和数据核对，但挂载列表断言失败；原升级前 inspect 未持久保存，不能断言失败一定由顺序导致。补充核对现有 Compose 挂载目标、旧卷创建时间、附件摘要和额外重启前后规范化挂载一致性后通过，限制已写入 test-upgrade.json。脚本已保存 checkpoint 并对挂载排序，正式升级一次通过。

业务验收第一次因为脚本漏传 Feedback 转需求必填 description 收到 422，修正测试请求后复用同一组纯角色账号完成验收，没有放宽产品校验。首次失败日志分别保留于服务器 `/opt/iterflow/upgrade-evidence/version-roles-198f831/attempt-1`、`attempt-2` 与 acceptance-attempt-1.log。

## Fresh Self-Review 与收尾

复核两端源镜像身份、迁移限定差异、备份摘要、三类纯角色发布与反向权限、测试保留标记及自动恢复配置均通过。保留最初失败与证据限制；本次为同一 Agent 的 Fresh Self-Review，不称独立终审。中文操作手册、API 指南、开发说明、任务状态和部署说明同步为已部署。合并源八项 CI 已通过；文档准备提交 d885b01 的八项 CI [39897913480](https://github.com/dede233/iterflow/actions/runs/39897913480) 通过。收尾提交以最终 master 的 GitHub Actions 结果为准，不重建产品镜像，不创建 tag/Release。
