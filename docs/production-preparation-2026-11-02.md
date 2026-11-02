# 2026-11-02 正式上线准备执行记录

## 授权与冻结基线

用户授权完成上线准备、将最新修改部署到保留测试环境验收、跑完八项 CI，通过后确认 master 无漂移再合并并同步 GitHub/Gitee；更新升级和回退文档。正式部署、正式数据库 migration/GRANT/restore/写入、tag/Release 不在本轮范围。

- 源分支：`codex/requirement-summary-no-progress`，本轮开始 `9faad46`（包含最新通知邮箱输入区隐藏）。
- GitHub master：`6fb84100be208e8faaa7fe7b7dd4b4533ad7efa5`。
- Gitee master：`10f6bfa6410c7836d7d43e402a175d56ad9577c7`；已知落后，不覆盖未知提交。合并前重新读取并核验祖先关系，使用非强推同步。
- 正式环境只读基线：`198f831d67e8b475975915b1824d711b949fb998`，`mysql57_0006`，health/ready 正常。测试 API/worker 为 `cd1f7ee`，schema `mysql57_0010`，Web 为 `1923a22`。

## 本轮准备内容

- 将最新邮箱标签/输入框与验证码行一同按“重新验证”展开，保留未验证直接展示及成功收起逻辑。
- [升级与回退操作清单](collaboration-workflow-upgrade.md) 修正实际双数据库迁移编号、多人验收规则、RDS 权限、维护窗口、API/Web/worker 配套、正式邮件站点及分阶段恢复边界。
- 同步 MySQL 包说明的 head、运行表权限数量和 worker 启动说明；不改历史迁移或正式数据。
- 本轮 CI 必须包含 backend、frontend、docker_smoke、s3、browser_smoke、backup_restore、mysql57 standard/portable 八项，不以旧 SHA 的结果替代最终提交。

## 执行记录

各项结果与原始失败在下文记录；最终 master 回执保存在本地交付目录。

## 正式执行边界

本轮完成后，仍需在正式部署授权及维护窗口内重新核对正式 SHA/schema、容量与 RDS 权限，取得一致的正式数据库/附件备份，并在隔离副本演练实际正式数据，再实施迁移和启用正式 SMTP。本轮不备份或复制正式业务内容，不将测试数据/账号/邮箱验证状态迁入正式。正式数据迁移耗时、最新 Brevo 额度与正式实际收件不能用 CI 或测试数据结果代替。

## 测试部署与最新界面验收

2026-11-02 12:37:39 +08:00，将候选 `2c503bfb216bcd61835de7a236a454ff8d6b0c5c` 的 Web 更新到 8444，镜像 `iterflow-web:production-prep-2c503bf`，config `sha256:04a13616c45a69de4662893bd59e06cf83cafad5b11b65d3a6e30b74041ef91e`。公网 index SHA256 为 `c6fcf16000bb02c91207360f4d326fe32023321ff4d606051328cb514db6fd78`，与构建产物一致。

- 仅修改 TEST WEB_IMAGE；API/worker 仍为 cd1f7ee，与候选后端源码无差异。API/Web healthy、ready 和 worker 运行通过，正式容器/配置及测试其他容器、运行/迁移/邮件配置摘要保持一致。
- 既有已验证账号：通知邮箱标签/输入框、验证码行和发送按钮初始均不存在；点击重新验证后一同显示；刷新后收起，PASS。
- 375px 输入外框和发送按钮同一行，均 44px 高，无横向溢出，PASS。未点击发送或修改偏好，不发送真实邮件。
- 服务端证据 `/opt/iterflow/upgrade-evidence/production-prep-2c503bf`；本地证据 `/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/production-prep-deployment-2c503bf`，含脚本、manifest、服务器回执截图、页面截图和 live-ui-result.json。

## 首轮 CI 发现与修复

候选 2c503bf 的 [CI 41389217401](https://github.com/dede233/iterflow/actions/runs/41389217401) 中 backup_restore 失败：恢复库实际已为 `0012_multiple_acceptance`，但演练脚本硬编码旧 `0011_notification_delivery`。修复为从已运行镜像读取 Alembic 唯一 head，备份前确认实际版本等于该 head，恢复后同时核对备份版本和 head；不放宽门禁、不跳过恢复或用重跑掩盖真实失败。`bash -n` 与 diff check PASS，新提交重新运行完整八项 CI。其余首轮结果及最终结果随后记录。

本地离线包构建首次被系统旧 Python 的 extractall(filter=...) 不支持拦截；改用已安装 Python 3.12，保留失败日志。后续 Docker 构建出现外部包 DNS 问题，处理与最终产物验证结果另记；不能将构建中视为已交付。

首轮 browser_smoke 为 186 PASS / 1 FAIL：真实发布主链脚本确认内容后直接点击“开始开发”，被新增的自动人员弹窗正确拦住。更新用例，明确断言人员弹窗出现、取消后关闭且需求仍为 CONFIRMED，再执行原开发/验收/发布/CAS/通知断言；没有 force click、跳过或移除业务门禁。该修复与恢复脚本修复一起进入新的完整八项 CI；中间 1565d0e 已启动的运行保留其结果，不视为最终门禁。

## 完整门禁与候选包

分支最终提交 `2cc10094ccc1bd2cb47687f40bee65f2786071c6` 的 [CI 41389886932](https://github.com/dede233/iterflow/actions/runs/41389886932) 于 2026-11-02 04:50:11 UTC 完成，**八项全部 PASS**：backend、frontend、docker_smoke、s3、browser_smoke（187 PASS）、backup_restore、mysql57 standard、mysql57 portable。首轮为 6 PASS / 2 FAIL；仅含恢复修复的中间 1565d0e [CI 41389660635](https://github.com/dede233/iterflow/actions/runs/41389660635) 为 7 PASS / 1 FAIL（旧浏览器用例），均保留证据，未降低门禁。

离线候选源 `2c503bf` 与最终分支的 backend、frontend/src、deploy/mysql57 和 spec 无差异；后续仅修复测试及文档。标准构建遇到本机 Docker DNS 故障，改用已验证 bc6f9b2 基础镜像（依赖锁及 Dockerfile 无变化）离线覆盖候选源码，pip check 及逐文件 app/alembic SHA256 比对通过。新建本地 MySQL 5.7.44 OFF/OFF 实例验证，不连接既有数据库；初次容器退出 139，保存日志后启动并确认认证连接正常才执行测试。包级 15 步主链、最小权限、revision 409、审计通知、附件权限、连续 3 次重启、备份及独立目标恢复（91 个触发器）全部 PASS，实例已停止。该结果不等同于真实正式数据演练。

- 包：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/production-candidate-2c503bf-offline/iterflow-production-candidate-2c503bf.tar.gz`，276888392 bytes。
- 包 SHA256：`4a2d5565973cae47137408095edd47af0524b8b2c016b440ffd07a7a5af991e0`。
- API config：`sha256:a24ba20e9cc11732914873672ed64f5d3a0971b0a9872a5cfd3fa1e21cfa2a05`；Web config 同上测试部署。
- 包含镜像、模板、升级回退说明、verification.json、image-configs.json、SHA256SUMS，不含真实数据库或 SMTP 配置。
- 只读服务器容量：磁盘可用 22.24 GiB，MemAvailable 748116 kB；测试 SMTP 为 Brevo 465/SSL、已选发件地址、8444 链接且保留收件白名单。未变更 SMTP 或发信。正式执行时须再次检查容量。

## master 合并检查

八项 CI 通过后重新 fetch / ls-remote：GitHub master 仍为 `6fb84100be208e8faaa7fe7b7dd4b4533ad7efa5`，Gitee master 仍为 `10f6bfa6410c7836d7d43e402a175d56ad9577c7`；后者是前者祖先，无未知漂移。使用现有 master 工作树 no-ff 合并分支，原有未跟踪 data/ 与历史证据文件不动。合并提交仅追加本轮验收证据，不改已验证产品代码。

合并后的 master 必须重新通过自身八项 CI，并普通推送 GitHub/Gitee、核对两端 SHA；最终 SHA、CI URL 与同步结果保存到本地交付目录 `production-preparation-final.json`，不能以分支结果替代。没有正式部署、正式库迁移/授权/恢复/写入或 tag/Release。
