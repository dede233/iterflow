# 三类角色的完整版本权限

2026-10-23，用户明确要求开发人员、产品负责人、研发负责人均能创建版本、安排需求、推进版本状态、执行检查和发布。实现分支 `codex/version-role-permissions`，基线 master `f98fff1f87c477c5f12194614d108e0ea4e2938c`。已合并为 `198f831d67e8b475975915b1824d711b949fb998` 并完成测试、正式环境升级；实际结果见 [部署记录](version-role-deployment-2026-10-23.md)。

## 权限与边界

| 基础角色 | 本次补齐 | 原数据范围 |
| --- | --- | --- |
| DEVELOPER 开发人员 | rd.version.create / edit / status / publish | SELF：本人创建或负责的版本 |
| PRODUCT_MANAGER 产品负责人 | rd.version.status / publish | ALL |
| DEVELOPMENT_LEAD 研发负责人 | rd.version.create / publish | SELF：本人创建或负责的版本 |

三类角色原本都有版本查看、需求查看及发布记录查看权限。安排需求使用版本编辑权限；添加、迁移和移出仍同时检查版本与需求各自范围。参与某需求不会自动取得整个版本权限。产品推进版本状态不等于推进需求状态；原需求编辑、状态、协作人员分配、开发本人确认资格不变。

后端仍使用权限码校验，前端沿用权限驱动按钮，不按角色名称硬编码或跳过检查。全员本人确认、非空开发名单、有效需求 DONE、版本 READY、revision CAS、唯一 Release、原子回滚、通知及审计全部保留。普通成员、设计、测试默认不能发布。系统基础角色仍为只读配置。

## 空库与已有库

新初始化使用更新后的基础 seed 默认授权。已有数据库通过新增迁移 PostgreSQL `0008_version_role_permissions` / MySQL `mysql57_0006` 补齐权限，历史迁移不改。新迁移在尚未基础 seed 的空库不预建权限目录，后续标准 seed 补全。

已有库只追加缺少的角色权限，不删除已有额外权限，不改变启停、数据范围、账号、密码、自定义角色或业务数据。角色 revision 增加一次，写 `ROLE_PERMISSION_UPDATE` 审计，来源标记为数据库迁移，操作者为空而非伪造管理员。重复执行不新增关系、revision 或审计。目标编码属于自定义角色、已初始化权限目录不完整时失败；DML 与审计在同一事务，异常全部回滚。

升级先在隔离测试环境备份、执行对应 Alembic upgrade head 并验收，再按当次授权更新正式环境。权限升级后刷新或重新登录更新页面菜单；后端从数据库读取当前权限。不能通过重跑 seed 升级已有库，因为 seed 会恢复角色启用状态和默认范围。MySQL readiness 严格匹配当前 head，部署时需在维护窗口配套升级 API 镜像与迁移；旧 API 不应继续承担新 head 的健康检查。前端业务代码未变化。

不提供自动 downgrade 撤权：无法可靠区分迁移前人工授予和本次新增的关系，需要基于升级前备份与审计制定受控回退方案。

## 验证

新增场景在真实 PostgreSQL 和 MySQL 5.7 执行：三角色分别登录、创建编辑版本、安排/迁移/移出需求、推进状态、检查和实际发布；全员确认前阻止 DONE/发布，旧 revision409、重复发布409、越界404、未授权403，故障注入确认发布事务回滚。

已有库迁移验证包括账号及业务数据保留、停用状态、自定义和额外授权保留、幂等、同名自定义角色阻断、缺失权限目录阻断，以及第二条审计写入失败后完整回滚。PostgreSQL 与 MySQL standard 的新增针对性场景各 7 项通过。完整 PostgreSQL 实库 61 项、前端单元 341 项与浏览器 160 项通过；全后端 399 项通过（S3 未配置项随后在独立本地 S3 实测 1 项通过）。前端类型、构建、契约类型、Ruff、Mypy 通过。

完整 MySQL 回归暴露预检查仍匹配旧 head 的问题，已更新为 mysql57_0006；mysql57_0005 仅在显式旧库预检查时接受，并继续检查开发确认触发器。本地 ARM Docker 上的 amd64 MySQL 重启曾出现入口脚本 mkdir 段错误，保留首次日志，未计为通过；恢复隔离容器后 standard 完整 72 项通过，包含三次连续重启、独立库与附件备份恢复。portable 首轮 68 项通过、4 项失败（旧 head 预检查与 standard 容器不可用），修正预检查后重跑又在本地 amd64 模拟重启时退出139，结果40通过、7失败、26错误。未计为通过或跳过门禁；以相同代码的原生 Linux CI standard/portable 完整验收继续验证，线上保持原版本。标准环境最后新增的旧 head 仅预检查允许/新 head 就绪校验另行实测。

Fresh Self-Review（同一 Agent）：检查三角色精确授权、无新增权限码/角色、旧授权与停用状态保留、迁移 CAS/审计/幂等/失败回滚、未改变状态机或发布事务、历史迁移与发布契约不变、API shape 未变、仅测试库恢复。源分支 CI 结果以 GitHub Checks 为准；没有合并 master、更新线上或创建 tag/Release。

## CI 依赖审计修复

首轮分支 CI `39895612356` 的前端依赖审计失败。核对上游公告后，在原主版本范围内更新 Vite 6.4.3 → 6.4.5、Vitest 系列 4.1.11 → 4.1.12、follow-redirects 1.16.0 → 1.16.1 及必要的测试依赖。全量及生产 npm audit 均为零漏洞，没有跳过审计。生成锁文件时本机 npm10 的 peer resolver 出现 edgesOut 异常，使用临时 npm12 生成，随后仍以 npm10 的标准 npm ci 验证安装，未更改全局 npm 或其他工作目录依赖。

上游依据：[Vitest](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8)、[Vite](https://github.com/vitejs/vite/security/advisories/GHSA-rq7h-c2jc-7f22)、[follow-redirects](https://github.com/follow-redirects/follow-redirects/security/advisories/GHSA-q3jh-wrc6-jgq8)。前端重新运行单元、类型、构建、bundle 与浏览器回归，最终分支 CI 以最后提交的 Checks 为准。
