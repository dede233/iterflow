# 发布记录与版本详情抽屉实机验收及线上升级

用户于 2026-10-13 授权：修改模块实机测试通过后合并，并升级正式与保留测试环境。保留账号、数据、附件及启动恢复配置；本次没有迁移、seed、restore、tag 或 Release 操作。

## 代码与门禁

产品源提交：`428d75c13baa2b7436c3c0bebd9ab5aef116f9c5`。合并前 GitHub/Gitee master 均为 `6bdf8017a243a4f47441837fe1c40ebe3fadec28`；no-ff 合并提交为 `9cdb396ad93f01c900e24a20458d00c623565cae`，已推送双远端。合并提交 frontend/backend/spec 与产品源提交相同。

前端 341 项单元测试、106 项构建产物浏览器回归通过，没有 skip；类型、构建、契约类型及 bundle 门禁通过。源分支 [八项 CI](https://github.com/dede233/iterflow/actions/runs/38336505284) 通过；合并 master [八项 CI](https://github.com/dede233/iterflow/actions/runs/38340263793) 的最终结果见证据文件。八项覆盖 PostgreSQL、MySQL 5.7 standard/portable、前端、浏览器、Docker、备份恢复与 S3。

## 真实测试环境验收

在 https://sx-kc.xyz:8444 的真实 API/MySQL 5.7.44-log 上验收，没有 API mock 或 SQLite 替代。375/390/768/1280/1440 五种屏宽验证发布记录→版本→发布记录、关闭保留列表、完整页返回、长内容及横向溢出；产品账号不显示发布入口。SELF 账号越界访问为404，无权限账号为403/禁止页，不泄露详情。

使用既有 ceshi002/003/012 验证新建反馈→受理→转需求→加入版本，以及双浏览器编辑。第一人保存成功，第二人旧 revision 保存返回409并显示冲突提示；版本抽屉推进开发、测试、待发布，未满足需求完成条件时发布按钮禁用；每名开发本人确认后，通过测试、完成及实际发布。需求和反馈变为 ONLINE，Release、通知及 VERSION_PUBLISH 审计正确，携带有效契约参数的重复发布返回409。最终成功用例对象为 Version 7 / Requirement 8 / Feedback 7 / Release 5，仅存在独立测试库。

七项必要实机用例已逐项通过。初次运行五个屏宽通过；权限用例选择器与登录成功提示冲突，发布用例通知字段断言和重复发布参数不符合契约。校正验收脚本后仅重跑受影响用例全部通过；未修改应用行为、未忽略失败或跳过测试。首次、第二次和最终运行证据保存在本地 `data/release-drawer-qa/`；各次已提交的独立测试业务记录保留为测试历史，不删除原数据或测试环境。

## 镜像与升级策略

两环境使用同一 linux/amd64 Web 镜像 `iterflow-web:release-drawer-428d75c13baa`，ID 为 `sha256:37a1bca756eb2813c9078a71fd9c2e2cd84891b16a62201dbf85d6cae5da3285`，运行用户101，镜像 revision 标签为源提交428d75c。静态包 SHA256 为 `4d65c80bb91b7ff607d18c84911acbf51ed35dd1ef87fc057334bc78ba200262`；实际首页引用 `index-CVHEwUY6.js`。

Docker Hub 网络失败导致标准服务器构建未成功，原失败日志保留；改用服务器已有且核验过的 Web 镜像作为同一 Nginx 运行时，替换本地 Node 22.23.2 构建并校验传输摘要的静态产物。未拉取新运行时或修改安全设置。API/backend/spec 未变，保留既有3fe3a42镜像，因此 API health.build_sha 仍为3fe3a42；不能把 Web 源提交误称为 API 镜像提交。

升级仅修改现有 images.env 的 WEB_IMAGE，冻结 API 写入、备份数据库与附件、读取全部表及文件摘要，重建 Web 后重复摘要核对，再解除冻结并等待健康。验证 HTTPS、新首页资产、API health/ready 以及 Web 重启后访问。保留原 API、Redis、数据库、卷及测试容器，不重新初始化。

测试环境最终升级 PASS：冻结窗口24张表和1个附件升级前后逐项一致；API/数据库/Redis身份、挂载和重启策略保留，正式环境基线未变。备份为 `/opt/iterflow/backups/release-drawer-test-pre-20261013T025546Z` 与 `/opt/iterflow/backups/release-drawer-test-post-20261013T025603Z`。前两次升级助手因 API 解冻后的健康等待及测试 API 无宿主端口的检查假设失败，均恢复旧 Web 并保留现场；修正助手后完整重跑成功，未削弱门禁。

服务器执行证据位于 `/opt/iterflow/upgrade-evidence/release-drawer-428d75c/`。备份目录700、文件600；证据仅保存校验摘要，密码和数据库导出不进入仓库或发布包。本次没有真实恢复演练。

## 手册与复查

更新 `docs/user-manual.md`，新增抽屉导航、完整页面入口、返回上下文与权限边界。使用 bundled Python/python-docx、LibreOffice 和 Poppler 导出 Word/PDF；第一次渲染中文缺字，改为 Arial Unicode MS 并明确配置本地字体后重新生成，8页全部逐页检查通过。文件及 SHA256 见 `docs/evidence/release-drawer/manual-render-20261013.json`。PDF/Word 保存于本机 `/Users/xiaweiyi/Developer/deliverables/iterflow/2026-10-13/`，不含密码。

Fresh Self-Review 为同一 Agent 复查：检查权限与 SELF 降级、revision409、抽屉导航与销毁、只读 Release、既有版本写接口和列表刷新、部署镜像来源及数据保留。未称独立审查。正式环境升级及重启验证通过；合并 master 八项 CI 全部通过。最终文档收口提交的八项 CI 以该提交的 GitHub Checks 为准，不重建已通过实机验收的前端产物。

## 正式环境结果

8443 升级及 Web 重启验证 PASS，HTTPS均为200，API health/ready正常。升级冻结窗口24张表摘要相同、现有附件0个；保留1名用户、1条需求，反馈/版本/Release原为0条。生产升级不创建测试业务记录。预备份 `/opt/iterflow/backups/release-drawer-production-pre-20261013T031733Z`，后备份 `/opt/iterflow/backups/release-drawer-production-post-20261013T031811Z`；`production-upgrade.json`记录完整数据校验及保留容器信息。API、Redis、四个测试容器保持身份、镜像、挂载及运行起点不变，原80/443站点配置保持不变。

正式环境当前没有版本和发布记录，因此真实编辑、发布、越权等写用例在隔离8444执行；8443仅验收实际页面、空态、相同静态镜像、健康与数据保留，不往正式库塞入验收记录。没有执行服务器整机重启，只执行了两环境各自Web容器重启。

两环境8个容器均healthy且采用unless-stopped，测试环境iterflow-test-stack及iterflow-test-nginx为enabled/active，cleanup_hold与retention.keep保留。Safari以既有正式管理员会话实际打开8443版本与发布记录空态；以测试产品负责人会话打开8444 Release #2，在同一抽屉切换版本#4、返回上个详情、关闭后保留version_id=4。浏览器验证没有修改正式业务记录。
