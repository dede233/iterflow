# 小程序品牌管理正式上线（2026-11-10）

用户确认TEST验收并完成候选八项准备后，明确授权进入上线流程。本次重新核对master无漂移、no-ff合并并同步GitHub/Gitee，完成最终master自身八项，再进行正式备份、真实数据隔离演练与短暂维护应用切换。无迁移、seed、权限修改或真实数据库恢复；保留独立TEST及原有数据、附件、账号/会话、审计/公告/已读、Release/目标记录与SMTP/JWT及其他运行/恢复配置。不创建tag/Release、不自动发布公告、不录入其余九品牌真实目标。

## 冻结与Git基线

冻结候选 `d6cfb815d7e1a240b7e2842842cc45f25348056a`，候选八项 [42803019010](https://github.com/dede233/iterflow/actions/runs/42803019010) attempt1全通过。backend/frontend/spec/deploy/tools/scripts/.github与用户已验收TEST `af3445d` 完全相同。准备及回退范围见 [上线准备](grouped-mini-program-production-preparation-2026-11-10.md) 和其交付目录最终报告。

本次合并前直接读取双远端，master均为 `0acf583969d102c98f2ef37c79d45ee8ac46dca6`，与准备结束及本地一致，候选为其后代。使用既有master工作树，保留其中不相交的未跟踪data/及历史测试凭据；merge新增本授权记录，其产品树必须仍等于候选，最终master需自己的八项，不能混用候选结果。

无凭据amd64四镜像包 `iterflow-grouped-mini-d6cfb815d7e1.tar.gz` 为277825946 bytes，SHA256 `7394055ffe7815a7f8adde9c36b2558b167043942ff00b894ce973c5cd9bbff7`。174个API文件与TEST相同，Web按冻结源码重新构建为140文件，新index SHA256 `5e35b7aa395ad244496830eec9d3459987edba8b7a9884f446950cba473321e7`，不声称与旧TEST字节相同。41层/OCI及classic config身份、模板无凭据、非root与pip及新隔离PG实跑均通过；真实amd64 MySQL两配置由候选CI完整包链证明。本机MySQL模拟退出139和宿主映射失败均保留在准备回执，不误报为通过。

## 执行门禁

正式起始已知 `0ef3e0d/mysql57_0016`，TEST `af3445d/mysql57_0016`；现场preflight必须重新核对主机、精确镜像ID/tag/既有继承label与API runtime BUILD_SHA、残留任务、磁盘/内存、35表/110触发器和恢复配置。资源不足不能沿用此前暂停TEST的一次性授权；先完成可做检查，再按当次安排处理。只用正常文件上传或核验身份的SSH/SFTP；宝塔网页终端只执行短控制命令，不传Base64/长脚本/文件块，不更改或重启宝塔。

正式镜像/配置及在线数据/附件取得一致恢复点；先在新internal隔离网络恢复真实备份，关闭SMTP/外发并验证全部35表完整行、结构/索引/外键/触发器/例程、附件和旧目标/历史兼容，演练不对正式写业务数据。保护并保留TEST，不导入TEST数据。无数据库迁移或GRANT。

演练通过后短暂维护，阻断入口并停止正式API/worker/Web写入者，取得新的最终一致数据库/附件备份，完整快照证明切换前后无丢失。先启动新API/Web，以实际runtime账号验证readiness和品牌目录相关实际查询、配置/挂载与SMTP/JWT保留，再恢复worker与原代理。正式验收只读，普通登录会话除外；不模拟发布/创建业务数据/群发通知。

恢复worker或开放业务后禁止无条件自动退旧，保留证据优先前向修复。之前仅在全部表/附件完全一致、旧应用身份和0016兼容性已证明时可回退旧应用，不回库。新品牌记录不得删除、降级或恢复旧备份来强行回退，不能恢复旧“所有目标完成才上线”门禁语义。

## 实际结果入口

本机交付目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-10/grouped-mini-production/`。

最终 `deployment-result.json` 与 `deployment-report.md` 记录完整master/双远端同SHA及八项、主机与两环境基线、备份/隔离演练、数据/附件/配置保留、维护窗口、健康和正式只读验收、TEST保护及异常/回退边界。本文件不提前声明部署完成，不为嵌入自身SHA循环提交；SQL、配置和实际凭据只留服务器受限目录。
