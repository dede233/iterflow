# 保留测试环境的开机恢复配置

本目录对应2026-10-12已存在并被用户保留的服务器测试项目 `iterflow-acceptance-20261012-753ebd`，不是创建空库或通用生产部署工具。脚本依赖服务器已有 `/opt/iterflow/acceptance-control/20261012/control.py` 和私有state.json；没有这些控制信息不能运行。宿主机已验证Python3.6、systemd239、Docker26.1.3、Compose2.38.2及宝塔原Nginx。

`autorecovery.py` 检查项目和既有卷，启动现有四容器、验证目标iterflow_acceptance，然后为独立8444入口读取Web IP并测试配置。只使用现存镜像/容器/卷；缺少数据目录或卷时失败，不启动空库初始化。错误写受保护日志。`review-nginx.template` 只复用现有证书路径，不包含证书或私钥。

两个systemd单元在 `/etc/systemd/system`，脚本和模板在对应测试stage；Compose acceptance.yml四处restart须为unless-stopped，现存容器策略同值。public区域8444/tcp须同时存在runtime/permanent规则，不能reload整个防火墙或修改原生产vhost。两个unit已enable，Docker/firewalld原已enable。

`install-autorecovery.py` 是一次配置及实际演练助手，已执行；重复install会因已有证据/unit而拒绝。manifest.json对应脚本/模板/unit摘要，不包含运行配置或数据库。上传原包及首次错误版本留在服务器作为证据；本仓库文件为修复后的最终版本。完整说明、命令、验收、回退边界见 [中文运维记录](../../docs/master-merge-and-autorecovery-2026-10-12.md)。

本次实际验证全服务冷启动、独立Nginx异常退出恢复、全表/附件保全及正式环境不变；未实际重启整台服务器。备份位于独立测试项目私有证据目录，定期备份尚未配置。后续测试升级后须reload入口以重新获取IP；正式和测试数据不自动同步。
