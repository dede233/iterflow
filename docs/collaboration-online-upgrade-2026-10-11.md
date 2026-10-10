# IterFlow 协作版本线上升级记录

本文件记录升级发生时的事实。随后用户授权将开发代码合入 master，见 [主分支合并记录](master-merge-2026-10-11.md)；该 Git 操作没有再次部署服务器，线上仍运行下述源 commit。

2026-10-11 00:53:18（Asia/Shanghai，UTC 2026-10-10T16:53:18Z），用户授权升级的 https://sx-kc.xyz:8443 已运行源 commit `2b37509aff342f8989ed21f61721d76c980141cb`。追加迁移、现有数据保留、健康检查、再次启动与升级前后备份通过；随后通过现有管理员会话完成只读页面验收。本次是开发分支快照部署，应用元数据仍为 1.8.1，没有创建新的正式 tag/Release。

## 实现范围和入口

分支 `codex/requirement-collaboration`，工作目录 `/Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation`。保留一名总负责人、多名开发与设计；按阶段选人，可按需经过 DESIGNING；每名开发本人确认后才允许 DONE 和发布。返工清空确认，新增和重新加入的开发人员待确认。常规状态推进无需原因，关闭和返工等动作仍需要原因。

接口文档已随镜像同步，可在系统设置进入并搜索、下载；仅超级管理员和研发负责人可读。当前文档列出 75 个接口，线上展开开发确认接口已核实本人资格、revision、DONE 与发布门禁说明。使用方法见 [操作手册](user-manual.md)，接口细节见 [集成指南](api-guide.md)，契约为 `spec/openapi-development.yaml`。

历史正式契约、PostgreSQL 迁移、tag 和 Release 未修改；master 仍为 `a38081af9097f691c8289e9301951a0360ea0af7`。后续文档收口 commit 与实际部署代码 commit 应分别识别。

## 部署前门禁

[GitHub Actions 38067092032](https://github.com/dede233/iterflow/actions/runs/38067092032) 对实际部署源 commit 八项成功：backend、frontend、browser_smoke、docker_smoke、backup_restore、s3，以及 standard/portable 两组 mysql57。

- 真实 MySQL 关系验证 17 passed，参数适配 3 passed，完整应用验收 64 passed，必要测试零跳过。
- PostgreSQL 全量 391 passed、1 项可选 S3 跳过；真实 PostgreSQL 专项 53 passed、零跳过，独立 S3 job 成功；契约 6 passed。
- 浏览器 job 161 passed，覆盖真实多账号主链、两名开发本人确认、0/2 和 1/2 阻断完成、2/2 完成、返工重置与重新确认、并发发布冲突。前端构建、类型和契约一致性门禁成功。
- 实际 linux/amd64 包在独立 MySQL 5.7.44 OFF/OFF 环境通过空库迁移与基础 seed、15 步主链、最小运行权限、CAS、通知审计、附件权限、连续三次重启、独立库与附件卷恢复，以及恢复后的 73 个触发器和新附件读写。
- 旧库升级专项 2 passed，验证已有账号、密码和需求保留，以及同名角色冲突会停止升级。Fresh Self-Review 为同一 Agent 复查，本轮没有外部独立终审。

Mac 包验收使用独立 Colima QEMU x86_64 VM，Docker context 为 `colima-iterflow-mysql57`；既有本地环境与 Preview 未操作。恢复演练仅在随机独立测试库、测试用户和附件卷进行，测试数据及凭据未进入部署包。证据见 [门禁与包验证摘要](evidence/collaboration-online/validation.json)。

首轮和修复轮 CI 的真实失败保留在本地 `data/collaboration-qa/ci-first-failure.log`、`ci-fix1-browser.log`、`ci-fix1-mysql.log`。修正了过期浏览器协作接口 mock、包主链缺少本人确认、PostgreSQL 恢复 head、MySQL 恢复触发器数量及跨账号旧 revision；没有删除门禁或忽略失败。

## 包和镜像

本地包：`/Users/xiaweiyi/Developer/deliverables/iterflow-collaboration-2b37509-linux-amd64.tar.gz`，276792434 bytes。

SHA256：`14053e4450443f7ef6c20b0e69c833044d4adc0971fcacd91fc0f1f520d18cb0`。服务器上传后重新计算，相同才允许解包。包含四个 linux/amd64 离线镜像，包内 manifest/verification 保留生成时的本地验证范围；实际线上证据单独记录。

| 镜像 | 服务器配置摘要 |
| --- | --- |
| iterflow-api:mysql57-2b37509aff34 | sha256:0fc629a4956f5ea55ef88c20418fa3dc782aa9eff7c75a8720386504a14d3d05 |
| iterflow-web:mysql57-2b37509aff34 | sha256:86a6079ea8d8d597e563c7006b5aa6c773f4dc9eaf2743fa06f815f9a0eeab49 |
| iterflow-mysql57-redis:8.2.2-amd64 | sha256:5d79a9ce29f8b3fe50fd5c07ee1bf654b5cec557b895835825bf6825d525e4f2 |
| iterflow-mysql57-client:5.7.44-amd64 | sha256:5107333e08a87b836d48ff7528b1e84b9c86781cc9f1748bbc1b8c42a870d933 |

首次升级在镜像 ID 检查处停止，尚未停服务或执行 DDL：本地 containerd 存储返回 OCI index/manifest ID，服务器 Docker Engine 26.1.3 返回配置 ID。随后核对原包的 OCI index/manifest/config 摘要、架构和所有 RootFS 层，四个镜像内容完全一致。仅修正一次性升级助手的身份比较，原助手保留为 `upgrade-server-original.py`；没有修改应用镜像、包 manifest 或压缩包。助手执行 SHA256 为 `cf10e6af09814ff700710395985b390134a8605487b59e5d7523a78ee462a0f4`，原助手为 `8e8e3c154ba5531856a96b6c9c38f5011fc30cb0652967942b16e05972afc9dd`。配置链接重试只接受与原保护文件完全相同的目标。

## 实际服务器升级

新目录 `/opt/iterflow/releases/iterflow-collaboration-2b37509`，旧目录 `/opt/iterflow/releases/mysql57-a147f4c-portable-197df967` 保留。复用原服务器受保护配置，不读取或替换密码、JWT_SECRET；未 seed 或重置账号。Docker Compose 为 2.38.2，仅升级 API/Web，保留 `iterflow-mysql57_uploads` 附件卷与现有 Redis。

实际专用数据库核实为 MySQL `5.7.44-log`、`utf8mb4/utf8mb4_bin`，large_prefix=OFF，应用会话 strict=ON；没有修改数据库全局参数。迁移从 `mysql57_0002` 追加 0003/0004/0005 至 `mysql57_0005`，触发器从 68 增至 73。所有原表行摘要与原角色、权限关系在迁移前后相同；新增两类角色和协作结构，不为既有需求代确认。

保留原 1 个账号、1 条需求、15 条迁移前审计记录；原库无反馈、版本、Release 或文件记录。线上现有需求保持已取消状态，协作面板与未分配负责人正常加载。文档读取产生的后续审计属于正常访问，不属于迁移写入。

原 80/443 站点配置 SHA256 保持 `491c4c78c19aac43e04bd75a73ff7155edf5a899deb029b0e3cb0749df5b7836`，原 `iterflow-production-redis` 容器 ID 未变。

升级时先停止 API/Web 写入并备份，迁移后启动验证，再停写生成升级后备份，随后再次启动验证。`/health` 源 SHA 为 2b37509，`/ready` MySQL/Redis/storage 全部 ok，HTTPS 根页面 200；匿名 auth/me 与受保护文档返回 401。管理员原会话刷新后仍可用，8 类角色与新接口文档正常。

## 备份和维护命令

升级前：`/opt/iterflow/backups/collaboration-pre-2b37509-20261010T165140Z`。

升级后：`/opt/iterflow/backups/collaboration-post-2b37509-20261010T165236Z`。

两处均包含 `database.sql`、`uploads.tar`、`SHA256SUMS` 和 `manifest.json`，命令返回码、非空 SQL/域触发器、附件归档结构及摘要已检查。目录 0700，文件 0600；备份留在受保护服务器目录，没有下载或导入其他环境。精确摘要见 [部署摘要](evidence/collaboration-online/deployment.json)。

```sh
cd /opt/iterflow/releases/iterflow-collaboration-2b37509
./dc.sh ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready

# 只读预检，不重新 seed
./dc.sh --profile init run --rm --no-deps -T migrate python -m app.cli.mysql_preflight

# 核对已生成备份
cd /opt/iterflow/backups/collaboration-post-2b37509-20261010T165236Z
sha256sum -c SHA256SUMS
```

后续备份需使用新的空备份目录、短暂停写并同时备份数据库与附件，命令参见 [MySQL 运维说明](../deploy/mysql57/README.md)。MySQL DDL 非原子，迁移失败须保留现场，不能 stamp、create_all 或盲目 downgrade。旧包不能直接配合已升级 schema 当作自动回滚；如需回退，应单独评估并授权恢复方案。本次没有线上 restore。

## 已验证范围和限制

完整多账号业务验收在隔离本地库与 CI 完成；线上验证范围为实际迁移、现有数据保留、镜像身份、HTTPS、匿名拒绝、重启、备份及管理员只读页面。没有在真实业务库创建测试账号或推进真实需求。线上数据库当前小版本已经核实，其他 MySQL 5.7 小版本、不同权限/参数或新的服务器不能沿用本次结果。

本次授权的线上升级已完成。开发和设计人员正式使用前，由管理员为每人创建独立账号并配置适当角色；不采用本地测试密码。开发确认必须本人操作，基础产品角色若需推进状态，应按职责配置相应角色组合。开发分支没有合并 master，没有 push master，也没有创建或重写 tag/Release。
