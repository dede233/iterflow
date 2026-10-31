# 反馈名称分支合并与测试环境开机恢复

2026-10-12用户明确授权“合并分支，然后配置重启自动恢复”。本次解除该分支此前不合并、不push master限制；不创建tag/Release，不重写历史，不再次更新正式应用，不执行数据库迁移、初始化或恢复。

## 合并与门禁

- 源分支 `codex/reference-display`，HEAD `5b9cf40e6a9d9617714f65d96c093b40fffe39c8`。
- 合并前本地、GitHub与Gitee master均为 `a58e9a3bbf59d6c6721ea8d330aadfa02ddd8254`，无外部漂移。
- no-ff合并提交 `b637e9b1e0dce62469764bfd457080d4f5aea508`，两个父提交分别为上述master与源HEAD；合并树与源分支完全相同，无冲突。
- [源分支八项CI](https://github.com/dede233/iterflow/actions/runs/38236589670) 和 [合并提交八项CI](https://github.com/dede233/iterflow/actions/runs/38237717677) 全部PASS，包含真实MySQL standard/portable、PostgreSQL、浏览器、部署与备份恢复。[分支结果](evidence/master-merge-20261012/branch-ci.json)、[合并结果](evidence/master-merge-20261012/merge-ci.json) 保存精确HEAD。
- 已推送两个远端master，随后追加本次恢复脚本、服务单元及中文说明。最终master须通过自身新的八项CI，再核对本地和两个远端SHA一致；不以分支CI代替。

在适配目录data下独立临时Git worktree操作，主仓库原分支 `codex/local-workspace-layout`、HEAD `ac388cd88c535d2eeb725157a0c6ba2b78a16379`及其他工作目录不覆盖。未提交测试日志、数据库、凭据和附件不参加合并。产品源仍为线上及8444验证过的 `3fe3a42`；本次恢复脚本不是应用镜像更新。

## 已配置的恢复行为

恢复目标仅为保留的测试项目 `iterflow-acceptance-20261012-753ebd`，入口 https://sx-kc.xyz:8444；正式8443不重启、不换镜像。配置源在 [deploy/test-environment](../deploy/test-environment/README.md)，不是通用空库部署包。

| 配置 | 已实现行为 |
| --- | --- |
| iterflow-test-stack.service | Docker与network-online之后启动，仅启动指定项目现有db/redis/api/web；等待健康，不构建、不拉新镜像、不重建、不迁移、不seed |
| 四个容器 | Compose覆盖配置和现存容器均为unless-stopped；既有卷、镜像和容器ID保留 |
| iterflow-test-nginx.service | firewalld及测试stack之后启动独立8444 TLS入口；前台Nginx由systemd管理，异常退出10秒后重启 |
| 动态代理地址 | 每次入口启动或reload都读取该项目当前Web私有IP，生成并测试独立Nginx配置，避免依赖旧IP |
| 防火墙 | 仅为public区域持久化原已开放的8444/tcp；runtime规则不变，不reload整个防火墙 |
| 保护条件 | state须保持用户保留授权；容器、卷须归属此项目，既有MySQL系统库和iterflow_acceptance数据目录须存在；缺失时停止，不初始化新库 |

Docker/firewalld原已enabled/active，不重启它们。服务文件在 `/etc/systemd/system/`，运行脚本与模板在 `/opt/iterflow/acceptance/iterflow-acceptance-20261012-753ebd/`；复用现有受保护测试配置及原证书路径，不复制密钥或生产数据。异常细节仅写私有日志，仓库不保存凭据、SQL或附件。

## 实际验收和限制

2026-10-12 18:55:47（UTC+8）完整恢复演练PASS：

1. systemd-analyze verify、既有配置目标及挂载检查通过，两个服务enabled/active，四容器healthy。
2. 在冻结测试API/Web写入后生成独立测试库dump及附件归档，并保存全表和文件摘要。
3. systemctl stop测试stack使入口及四服务全部停止；只启动入口服务，其依赖自动恢复数据库、Redis、API和Web，并恢复HTTPS200。
4. 再次冻结写入，24张表全部行摘要及1个附件文件摘要前后一致；四容器ID、镜像及全部挂载属性一致。
5. reload测试入口通过；对经归属校验的独立Nginx主进程注入异常退出，systemd自动恢复，主PID从510351变为511667，HTTPS恢复200。
6. 正式四容器ID/镜像/启动时间、原站vhost摘要及health与原baseline完全相同。

首次演练最终Mounts原始数组比较未通过。复核全部挂载属性一致后，修正为按Destination排序比较所有属性，仍检查容器ID和镜像；完整重新演练通过。首次失败、原脚本、原manifest、快照与备份保留，不删除或改写失败证据。修复安装/验收脚本SHA256为 `335e398cd2525d3a3df12db48149ad25b06748b553fa06314f354c0fae7da159`。

[脱敏验收摘要](evidence/master-merge-20261012/autorecovery.json) 记录备份SHA256和范围。服务器完整回执为 `/opt/iterflow/acceptance-evidence/iterflow-acceptance-20261012-753ebd/autorecovery-20261012/rehearsal.json`；成功演练备份位于同目录的 `rehearsal-20261012T105420Z`，文件600、目录700，仅属于独立测试库和测试存储，没有restore。

未重启整台服务器，也未重启Docker、firewalld、原站或正式服务。因此本次证明服务开机配置、启动依赖、同一启动路径的全服务冷启动与入口异常恢复，不能写成已完成整机重启验收。定期备份仍未配置。

Fresh Self-Review由同一Agent执行：核对合并父提交和树、历史契约/迁移/标签不变，测试资源归属及缺失数据保护，单端口规则变化、同一镜像/容器/卷和业务数据保全、异常恢复证据与文档范围；不称外部独立审查。

## 日常查看和恢复

查看服务及开机状态（在服务器终端执行）：

```bash
systemctl status iterflow-test-stack iterflow-test-nginx --no-pager
systemctl is-enabled iterflow-test-stack iterflow-test-nginx
```

测试Web容器更新完成且健康后刷新代理；证书路径内容续期后也使用该命令：

```bash
systemctl reload iterflow-test-nginx
```

仅重启测试入口：

```bash
systemctl restart iterflow-test-nginx
```

完整停启测试服务，会使8444短时不可用，保留数据卷：

```bash
systemctl stop iterflow-test-stack
systemctl start iterflow-test-nginx
```

服务stop仅为当前运行停止，仍会在下次开机启动。需要跨重启维护时另行停用相应unit；后续移除仍须用户新的明确指令，先disable/stop这两个服务，再按项目归属处理，不能只kill PID或全局prune。不要直接重复运行install脚本覆盖现存服务，也不要删除卷或通过清库恢复。
