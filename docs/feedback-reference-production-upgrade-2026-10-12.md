# 反馈名称显示修复正式环境更新记录

2026-10-12，用户明确授权“更新正式环境，提交推送代码，写中文说明”。本次范围为已在8444独立测试环境验收的反馈提交人、系统与模块名称显示修复，以及测试环境保留和先测试后正式更新的部署规则。正式更新、重启和数据保全验证已完成，结果 PASS（2026-10-12 18:17:31，UTC+8）。

## 代码与验收基线

- 工作分支：`codex/reference-display`；目录 `/Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation`。
- 实际产品源 commit：`3fe3a42c6116024acf2636921c7849f48f952bc8`；其后提交仅为中文流程说明、文档和验收记录，产品树相同。
- 更新前 master：`a58e9a3bbf59d6c6721ea8d330aadfa02ddd8254`；更新前正式服务源为 `2b37509aff342f8989ed21f61721d76c980141cb`。
- 本次提交及推送工作分支到 GitHub/Gitee，不合并或推送 master，不创建 tag/Release，不改写历史。
- 本地 MySQL65项必要用例全部通过、PostgreSQL15项、反馈/契约/文档56项、前端336项以及构建/类型/Ruff/Mypy通过。MySQL首次两项环境失败及修正后的重跑结果保留，详见 [修复记录](feedback-reference-display-fix.md)。
- 8444三账号HTTPS权限核验及Safari完整/抽屉页面验收通过，用户已查看确认无问题；测试环境、数据库、附件和测试账号保留。

## 部署范围与顺序

先完成本次新分支的八项CI，不能用旧分支CI替代。正式服务使用8444已验证的相同API/Web镜像内容，不导入任何测试账号、密码、数据库或附件。

正式更新前核对服务目录、镜像与源SHA、数据库迁移head/约束、原站配置和存储挂载。短暂停止正式API/Web写入，生成受保护的正式数据库与附件一致备份，并核对非空、摘要和归档结构。新部署目录复用既有受保护配置，不读取或替换用户密码和JWT_SECRET。

本次无驱动、依赖、数据库迁移、seed、权限、状态机或业务关系变更，只更新API/Web。保持原生产数据库、附件卷、Redis和80/443/8443入口；8444独立测试项目不重建或清理。保留旧目录和旧镜像作为应用回退依据，不执行线上restore。

更新后核对health/readiness、HTTPS、匿名拒绝、受保护文档及现有管理员只读页面，比较数据库所有表与附件摘要，验证应用按依赖重启，再生成更新后备份。正式库不创建多账号测试数据，不推进既有需求或发布业务版本。

## 实际结果

本次 [八项 CI](https://github.com/dede233/iterflow/actions/runs/38232487301) 在精确 HEAD `e4c6f8d5942e14cfcdc294cd50f965a8c1d3f939` 全部 PASS：backend、frontend、browser_smoke、docker_smoke、backup_restore、s3、mysql57 standard/portable。MySQL 两配置各65项通过且0跳过，PostgreSQL专项54项通过，浏览器161项通过。最终收口提交仅更新本文等文档和脱敏证据，不重新构建镜像；CI HEAD 与实际产品源及最终文档 HEAD 分别记录，不能声称 CI 在最终文档 HEAD 运行。

正式入口 https://sx-kc.xyz:8443；当前目录 `/opt/iterflow/releases/iterflow-reference-display-3fe3a42`。API/Web 均为 linux/amd64，与8444已验收镜像的内容 ID 完全相同，仅添加生产镜像标签：

| 服务 | 镜像标签 | 内容 ID（Docker image ID） |
| --- | --- | --- |
| API | iterflow-api:mysql57-3fe3a42c6116 | sha256:735bd73784c2f5e57b6f4b47de0e93c9fe082a3b19cd052ecadaea9af3a62de4 |
| Web | iterflow-web:mysql57-3fe3a42c6116 | sha256:5c8f46817a40a4ea7037aaa116d8f913a1ded5b96e8e84b8fbd9d228c928670 |

实际 health.build_sha 为完整 `3fe3a42c6116024acf2636921c7849f48f952bc8`；ready 的 MySQL、Redis、storage 全部 ok。API/Web 顺序停止并重新启动后仍健康；HTTPS首页200且新JS资源正确；匿名 auth/me 与受保护 OpenAPI 均401。原站 vhost 内容摘要、两项生产 Redis 和四项测试容器 ID/镜像/启动时间/卷保持不变。

正式数据库24张表逐表比较行数和所有行内容摘要，部署前后一致。附件卷当时无文件，空目录归档及前后摘要一致；不能把此次空附件核对称为新增真实文件恢复验收。保留既有账号和业务数据，未迁移、初始化、清库或线上恢复，未导入测试账号或附件。

Safari刷新正式页面后，现有管理员会话继续可用、用户列表1个账号、反馈列表0条；受保护接口文档正常加载，并已展示三个新响应字段。正式库没有反馈，不为验证而新增正式业务记录；名称完整页/抽屉、多角色和DataScope验证已在8444完成。读取受保护文档产生正常审计，不属于部署期间的数据变化。8444刷新后原验收产品账号仍可访问，4条反馈保留。

## 备份、回退依据及失败记录

- 更新前：`/opt/iterflow/backups/reference-display-pre-3fe3a42-20261012T101559Z`。
- 更新后：`/opt/iterflow/backups/reference-display-post-3fe3a42-20261012T101648Z`。
- 两套均包含 database.sql、uploads.tar、manifest.json、SHA256SUMS，目录0700、备份文件0600。已核对dump表结构/触发器、归档路径及文件SHA256；未执行正式库恢复。
- 原目录 `/opt/iterflow/releases/iterflow-collaboration-2b37509` 与旧API/Web镜像保留，供另行授权的应用回退使用；回退前仍须核对数据库兼容性和现存数据，不能盲目恢复旧库覆盖新业务写入。
- 服务器完整证据 `/opt/iterflow/upgrade-evidence/reference-display-3fe3a42/deployment.json`；仓库仅存 [脱敏摘要](evidence/feedback-reference-production/deployment-summary.json) 和 [CI结果](evidence/feedback-reference-production/ci-gate.json)，不存密码、Token、JWT_SECRET、数据库内容、附件或原始命令日志。

首次部署助手在备份与切换前，因对服务器单空格缩进的只读脚本机械注入四空格而失败，自动重启原版并验证旧health。首次失败回执、助手和保护日志完整保留。改为独立前置数据库目标检查、先语法编译，实际用新旧镜像只读检查一致后才重试；第二次部署全部通过。修复助手SHA256为 `58b2d530f45455064e35b5a71d09f819775166ad5160a92770a8a35e764308f3`。没有忽略失败或降低数据保全门禁。

保留测试控制器已将当前正式源/目录与baseline更新到3fe3a42，旧baseline和控制器保存为历史证据；retention.keep与cleanup_hold继续生效。该次正式更新结束时测试环境重启自动恢复、定期备份尚未配置。后续用户授权已配置开机恢复并完成演练，见 [合并与运维记录](master-merge-and-autorecovery-2026-10-12.md)；定期备份仍待配置。

本次 Fresh Self-Review 由同一Agent完成：核对相同镜像内容、正式配置目标、零迁移/seed/restore、备份保护、数据比较、原站/Redis/测试保护、契约字段及文档事实，不称外部独立终审。
